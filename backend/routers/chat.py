import json
import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from database import get_db
from auth import get_current_user
from ws_auth import ws_authenticate
from rag import retrieve_chunks
from config import OLLAMA_HOST, LLM_MODEL, LLM_TIMEOUT, MAX_EXCHANGES_PER_DOC

log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# ---------------------------------------------------------------------------
# Preference-to-prompt mappings
# ---------------------------------------------------------------------------

STYLE_INSTRUCTIONS = {
    "visual": "Use bullet points and bold **key terms**. Structure your answer with clear visual hierarchy. Keep it scannable.",
    "auditory": "Write in a warm, conversational tone as if explaining out loud to a friend. Use natural speech patterns.",
    "reading": "Write in clear, well-structured paragraphs with full context and nuance. Use proper prose, no bullet points.",
    "mixed": "Use short paragraphs with occasional bold key terms. Balance structure with readability.",
}

DEPTH_INSTRUCTIONS = {
    "brief": "Keep your answer to 2-3 sentences maximum. Only the key point, nothing extra.",
    "balanced": "Answer in 4-6 sentences. Cover the main idea with enough context to understand.",
    "detailed": "Give a thorough answer in 6-10 sentences. Include examples, context, and connections to related concepts.",
}

USE_CASE_INSTRUCTIONS = {
    "exam": "Focus on definitions, facts, and testable information. Be precise and direct. Mention any formulas or key terms worth memorizing.",
    "work": "Focus on practical takeaways, action items, and decisions. Be concise and professional. Highlight what matters for execution.",
    "learning": "Focus on understanding — explain why things work the way they do. Use analogies if helpful. Make it interesting.",
    "research": "Focus on methodology, evidence, findings, and limitations. Be analytical and precise. Reference specific sections when possible.",
}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    upload_id: int
    question: str

class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    exchange_count: int
    limit: int

class HistoryItem(BaseModel):
    id: int
    user_message: str
    ai_response: str
    sources: list[str]
    created_at: str

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_qa_ready(upload_id: int) -> None:
    db = get_db()
    try:
        row = db.execute(
            "SELECT qa_ready FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Upload not found")
        if not row["qa_ready"]:
            raise HTTPException(
                status_code=409,
                detail="Document is still processing. Chat will be available once embeddings are complete.",
            )
    finally:
        db.close()


def _check_exchange_limit(upload_id: int) -> int:
    db = get_db()
    try:
        count = db.execute(
            "SELECT COUNT(*) as cnt FROM chat_history WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()["cnt"]
        if count >= MAX_EXCHANGES_PER_DOC:
            raise HTTPException(
                status_code=429,
                detail=f"Exchange limit reached ({MAX_EXCHANGES_PER_DOC} questions per document).",
            )
        return count
    finally:
        db.close()


def _verify_upload_ownership(upload_id: int, user_id: int) -> None:
    db = get_db()
    try:
        row = db.execute(
            "SELECT id FROM uploads WHERE id = ? AND user_id = ?",
            (upload_id, user_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Upload not found")
    finally:
        db.close()


def _get_user_preferences(user_id: int) -> dict:
    db = get_db()
    try:
        row = db.execute(
            "SELECT learning_style, content_depth, use_case "
            "FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return {
                "learning_style": "mixed",
                "content_depth": "balanced",
                "use_case": "learning",
            }
        return {
            "learning_style": row["learning_style"],
            "content_depth": row["content_depth"],
            "use_case": row["use_case"],
        }
    finally:
        db.close()


def _build_chat_prompt(question: str, chunks: list[dict], prefs: dict) -> str:
    context = "\n\n".join(f"[{i+1}] {c['chunk']}" for i, c in enumerate(chunks))
    style = STYLE_INSTRUCTIONS.get(prefs["learning_style"], STYLE_INSTRUCTIONS["mixed"])
    depth = DEPTH_INSTRUCTIONS.get(prefs["content_depth"], DEPTH_INSTRUCTIONS["balanced"])
    use_case = USE_CASE_INSTRUCTIONS.get(prefs["use_case"], USE_CASE_INSTRUCTIONS["learning"])

    return f"""You are a helpful learning assistant for Verso. Answer the user's question based on the provided context from their uploaded document. Always be helpful — if the question is broad (like "tell me about this" or "summarize"), provide an overview of the key topics covered in the context. Only say you can't answer if the context is completely unrelated to the question.

CONTEXT FROM DOCUMENT:
{context}

ANSWER FORMAT RULES:
{style}

ANSWER LENGTH:
{depth}

ANSWER FOCUS:
{use_case}

Cite which chunk(s) [1], [2], [3] you used in your answer.

USER QUESTION: {question}

ANSWER:"""


async def _generate(prompt: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_ctx": 4096},
            },
            timeout=LLM_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()


async def _generate_stream(prompt: str):
    """Async generator that yields tokens from Ollama streaming API."""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "options": {"num_ctx": 4096},
            },
            timeout=LLM_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue


def _build_sources(chunks: list[dict]) -> list[str]:
    return [f"Chunk {c['index'] + 1} (score: {c['score']:.2f})" for c in chunks]


def _save_exchange(
    upload_id: int, user_message: str, ai_response: str, sources: list[str]
) -> int:
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO chat_history (upload_id, user_message, ai_response, sources) VALUES (?, ?, ?, ?)",
            (upload_id, user_message, ai_response, json.dumps(sources)),
        )
        db.commit()
        return cursor.lastrowid
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/chat/ask", response_model=AskResponse)
async def ask(req: AskRequest, user: dict = Depends(get_current_user)):
    _verify_upload_ownership(req.upload_id, user["id"])
    _check_qa_ready(req.upload_id)
    current_count = _check_exchange_limit(req.upload_id)

    prefs = _get_user_preferences(user["id"])

    try:
        chunks = await retrieve_chunks(req.question, req.upload_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not chunks:
        raise HTTPException(status_code=404, detail="No relevant content found in document")

    prompt = _build_chat_prompt(req.question, chunks, prefs)

    try:
        answer = await _generate(prompt)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM generation timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e.response.status_code}")

    sources = _build_sources(chunks)
    _save_exchange(req.upload_id, req.question, answer, sources)

    return AskResponse(
        answer=answer,
        sources=sources,
        exchange_count=current_count + 1,
        limit=MAX_EXCHANGES_PER_DOC,
    )


@router.get("/chat/history/{upload_id}")
async def get_history(upload_id: int, user: dict = Depends(get_current_user)):
    _verify_upload_ownership(upload_id, user["id"])
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id, user_message, ai_response, sources, created_at "
            "FROM chat_history WHERE upload_id = ? ORDER BY created_at ASC",
            (upload_id,),
        ).fetchall()
        return [
            HistoryItem(
                id=row["id"],
                user_message=row["user_message"],
                ai_response=row["ai_response"],
                sources=json.loads(row["sources"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
    finally:
        db.close()


@router.get("/chat/status/{upload_id}")
async def chat_status(upload_id: int, user: dict = Depends(get_current_user)):
    _verify_upload_ownership(upload_id, user["id"])
    db = get_db()
    try:
        upload = db.execute(
            "SELECT qa_ready FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        if upload is None:
            raise HTTPException(status_code=404, detail="Upload not found")

        count = db.execute(
            "SELECT COUNT(*) as cnt FROM chat_history WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()["cnt"]

        return {
            "qa_ready": bool(upload["qa_ready"]),
            "exchange_count": count,
            "limit": MAX_EXCHANGES_PER_DOC,
            "remaining": max(0, MAX_EXCHANGES_PER_DOC - count),
        }
    finally:
        db.close()


@router.websocket("/ws/chat/{upload_id}")
async def ws_chat(ws: WebSocket, upload_id: int):
    await ws.accept()
    user = await ws_authenticate(ws)
    if user is None:
        return

    # Verify ownership and qa_ready
    db = get_db()
    try:
        row = db.execute(
            "SELECT qa_ready FROM uploads WHERE id = ? AND user_id = ?",
            (upload_id, user["id"]),
        ).fetchone()
    finally:
        db.close()

    if not row:
        await ws.send_text(json.dumps({"type": "error", "detail": "Upload not found"}))
        await ws.close(code=1008)
        return

    if not row["qa_ready"]:
        await ws.send_text(json.dumps({"type": "error", "detail": "Document still processing"}))
        await ws.close(code=1008)
        return

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "detail": "Invalid JSON"}))
                continue

            question = msg.get("question", "").strip()
            if not question:
                await ws.send_text(json.dumps({"type": "error", "detail": "Empty question"}))
                continue

            # Check exchange limit
            db = get_db()
            try:
                count = db.execute(
                    "SELECT COUNT(*) as cnt FROM chat_history WHERE upload_id = ?",
                    (upload_id,),
                ).fetchone()["cnt"]
            finally:
                db.close()

            if count >= MAX_EXCHANGES_PER_DOC:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "detail": f"Exchange limit reached ({MAX_EXCHANGES_PER_DOC} questions per document).",
                }))
                continue

            # Retrieve chunks
            try:
                chunks = await retrieve_chunks(question, upload_id)
            except Exception as e:
                await ws.send_text(json.dumps({"type": "error", "detail": str(e)}))
                continue

            if not chunks:
                await ws.send_text(json.dumps({"type": "error", "detail": "No relevant content found"}))
                continue

            prefs = _get_user_preferences(user["id"])
            prompt = _build_chat_prompt(question, chunks, prefs)
            sources = _build_sources(chunks)

            await ws.send_text(json.dumps({"type": "stream_start", "sources": sources}))

            # Stream tokens
            full_answer = []
            try:
                async for token in _generate_stream(prompt):
                    full_answer.append(token)
                    await ws.send_text(json.dumps({"type": "token", "content": token}))
            except Exception as e:
                await ws.send_text(json.dumps({"type": "error", "detail": f"Generation failed: {e}"}))
                continue

            answer = "".join(full_answer).strip()
            _save_exchange(upload_id, question, answer, sources)

            await ws.send_text(json.dumps({
                "type": "stream_end",
                "exchange_count": count + 1,
                "limit": MAX_EXCHANGES_PER_DOC,
            }))

    except WebSocketDisconnect:
        pass
