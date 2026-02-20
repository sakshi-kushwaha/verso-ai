import json
import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from database import get_db
from auth import get_current_user
from ws_auth import ws_authenticate
from rag import retrieve_chunks
from config import OLLAMA_HOST, CHAT_MODEL, LLM_TIMEOUT, MAX_EXCHANGES_PER_DOC

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
    summary: str | None = None

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


MAX_HISTORY_CHARS = 2000  # Hard cap on conversation history to stay within context window

GREETING_PATTERNS = {
    "hi", "hello", "hey", "hola", "greetings", "good morning",
    "good afternoon", "good evening", "howdy", "sup", "yo",
    "what's up", "whats up", "thank you", "thanks", "thankyou",
    "thank u", "thx", "ty", "bye", "goodbye", "see you",
    "ok", "okay", "cool", "got it", "nice", "great",
}


THANKYOU_PATTERNS = {"thank you", "thanks", "thankyou", "thank u", "thx", "ty"}
BYE_PATTERNS = {"bye", "goodbye", "see you"}
ACKNOWLEDGEMENT_PATTERNS = {"ok", "okay", "cool", "got it", "nice", "great"}


def _is_greeting(text: str) -> bool:
    """Check if the message is a simple greeting/pleasantry (should not count as an exchange)."""
    cleaned = text.lower().strip().rstrip("!?.,:;")
    return cleaned in GREETING_PATTERNS


def _get_greeting_reply(text: str, name: str) -> str:
    """Return an appropriate reply based on the type of pleasantry."""
    cleaned = text.lower().strip().rstrip("!?.,:;")
    if cleaned in THANKYOU_PATTERNS:
        return f"You're welcome, {name}! Got more questions? I'm here."
    if cleaned in BYE_PATTERNS:
        return f"Bye {name}! Come back anytime you need help."
    if cleaned in ACKNOWLEDGEMENT_PATTERNS:
        return "Anything else you'd like to know about this document?"
    return f"Hey {name}! What are your questions about this document?"


def _get_user_name(user_id: int) -> str:
    """Get the user's display name for greeting responses."""
    db = get_db()
    try:
        row = db.execute(
            "SELECT display_name FROM user_preferences WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row and row["display_name"]:
            return row["display_name"]
        row = db.execute(
            "SELECT name FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row["name"] if row else "there"
    finally:
        db.close()


def _enrich_query(question: str, prior_exchanges: list[dict]) -> str:
    """Enrich a vague follow-up question with context from the last exchange.

    If the current question is short/vague (e.g. "explain more", "what about that"),
    prepend the last question so RAG retrieval finds relevant chunks.
    """
    if not prior_exchanges:
        return question
    # Short or vague questions likely need context
    words = question.lower().split()
    vague_markers = {"more", "that", "this", "it", "those", "these", "above",
                     "explain", "elaborate", "detail", "why", "how", "what"}
    is_vague = len(words) <= 5 and any(w in vague_markers for w in words)
    if is_vague:
        last_q = prior_exchanges[-1]["user"]
        return f"{last_q} {question}"
    return question


def _get_recent_exchanges(upload_id: int, limit: int = 3) -> list[dict]:
    """Return the last `limit` exchanges for this upload, oldest-first."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT user_message, ai_response FROM chat_history "
            "WHERE upload_id = ? ORDER BY created_at DESC LIMIT ?",
            (upload_id, limit),
        ).fetchall()
        return [
            {"user": row["user_message"], "ai": row["ai_response"]}
            for row in reversed(rows)
        ]
    finally:
        db.close()


def _build_chat_prompt(
    question: str,
    chunks: list[dict],
    prefs: dict,
    prior_exchanges: list[dict] | None = None,
) -> str:
    context = "\n\n".join(f"[{i+1}] {c['chunk']}" for i, c in enumerate(chunks))
    style = STYLE_INSTRUCTIONS.get(prefs["learning_style"], STYLE_INSTRUCTIONS["mixed"])
    depth = DEPTH_INSTRUCTIONS.get(prefs["content_depth"], DEPTH_INSTRUCTIONS["balanced"])
    use_case = USE_CASE_INSTRUCTIONS.get(prefs["use_case"], USE_CASE_INSTRUCTIONS["learning"])

    # Build conversation history section
    history_section = ""
    if prior_exchanges:
        history_lines = []
        for ex in prior_exchanges:
            history_lines.append(f"Student: {ex['user']}")
            ai_text = ex["ai"]
            if len(ai_text) > 300:
                ai_text = ai_text[:300] + "..."
            history_lines.append(f"Verso: {ai_text}")
        history_section = "\nPRIOR CONVERSATION:\n" + "\n".join(history_lines) + "\n"
        if len(history_section) > MAX_HISTORY_CHARS:
            history_section = history_section[:MAX_HISTORY_CHARS] + "\n[...conversation truncated]\n"

    return f"""You are a helpful learning assistant for Verso. You MUST ONLY answer questions using the provided context from the user's uploaded document. If the question is broad (like "tell me about this" or "summarize"), provide an overview of the key topics covered in the context. If the question is NOT related to or answerable from the document context, respond with: "Oops! That doesn't seem to be covered in this document. Try asking something related to what's in your uploaded file!"

If the user refers to something discussed earlier, use the prior conversation to maintain continuity.

CONTEXT FROM DOCUMENT:
{context}
{history_section}
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
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": CHAT_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": 2048},
            },
            timeout=LLM_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()


async def _generate_stream(prompt: str):
    """Async generator that yields tokens from Ollama streaming API."""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": CHAT_MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {"num_ctx": 2048},
            },
            timeout=LLM_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("response", "")
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

async def _generate_summary(upload_id: int) -> str:
    """Generate a conversation summary, save it, and erase detailed history."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT user_message, ai_response FROM chat_history "
            "WHERE upload_id = ? ORDER BY created_at ASC",
            (upload_id,),
        ).fetchall()
    finally:
        db.close()

    if not rows:
        return ""

    conversation_lines = []
    for i, row in enumerate(rows, 1):
        conversation_lines.append(f"Q{i}: {row['user_message']}")
        ai_text = row["ai_response"]
        if len(ai_text) > 200:
            ai_text = ai_text[:200] + "..."
        conversation_lines.append(f"A{i}: {ai_text}")
    conversation_text = "\n".join(conversation_lines)

    summary_prompt = f"""Summarize this Q&A conversation about a document in 3-5 bullet points. Focus on the key topics discussed and main insights the student learned. Be concise.

CONVERSATION:
{conversation_text}

SUMMARY (3-5 bullet points):"""

    try:
        summary = await _generate(summary_prompt)
    except Exception:
        summary = "Summary could not be generated."

    db = get_db()
    try:
        # Get next session number
        session_num = db.execute(
            "SELECT COALESCE(MAX(session_number), 0) + 1 as next FROM chat_summaries WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()["next"]

        # Save to chat_summaries table (permanent, survives new sessions)
        db.execute(
            "INSERT INTO chat_summaries (upload_id, summary, session_number) VALUES (?, ?, ?)",
            (upload_id, summary, session_num),
        )

        # Mark current session as complete
        db.execute(
            "UPDATE uploads SET chat_summary = ? WHERE id = ?",
            (summary, upload_id),
        )

        # Delete chat history for this session
        db.execute(
            "DELETE FROM chat_history WHERE upload_id = ?",
            (upload_id,),
        )
        db.commit()
    finally:
        db.close()

    return summary


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/chat/ask", response_model=AskResponse)
async def ask(req: AskRequest, user: dict = Depends(get_current_user)):
    _verify_upload_ownership(req.upload_id, user["id"])
    _check_qa_ready(req.upload_id)

    # Greetings don't count as an exchange
    if _is_greeting(req.question):
        name = _get_user_name(user["id"])
        db = get_db()
        try:
            count = db.execute(
                "SELECT COUNT(*) as cnt FROM chat_history WHERE upload_id = ?",
                (req.upload_id,),
            ).fetchone()["cnt"]
        finally:
            db.close()
        return AskResponse(
            answer=_get_greeting_reply(req.question, name),
            sources=[],
            exchange_count=count,
            limit=MAX_EXCHANGES_PER_DOC,
        )

    current_count = _check_exchange_limit(req.upload_id)

    prefs = _get_user_preferences(user["id"])
    prior = _get_recent_exchanges(req.upload_id)
    search_query = _enrich_query(req.question, prior)

    try:
        chunks = await retrieve_chunks(search_query, req.upload_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not chunks:
        raise HTTPException(status_code=404, detail="No relevant content found in document")

    prompt = _build_chat_prompt(req.question, chunks, prefs, prior_exchanges=prior)

    try:
        answer = await _generate(prompt)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM generation timed out. Please try again.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e.response.status_code}")

    sources = _build_sources(chunks)
    _save_exchange(req.upload_id, req.question, answer, sources)

    new_count = current_count + 1
    summary = None
    if new_count >= MAX_EXCHANGES_PER_DOC:
        try:
            summary = await _generate_summary(req.upload_id)
        except Exception as e:
            log.error(f"Summary generation failed for upload {req.upload_id}: {e}")

    return AskResponse(
        answer=answer,
        sources=sources,
        exchange_count=new_count,
        limit=MAX_EXCHANGES_PER_DOC,
        summary=summary,
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
            "SELECT qa_ready, chat_summary FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        if upload is None:
            raise HTTPException(status_code=404, detail="Upload not found")

        count = db.execute(
            "SELECT COUNT(*) as cnt FROM chat_history WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()["cnt"]

        has_summary = bool(upload["chat_summary"])
        # If summary exists, history was cleared — report full limit used
        effective_count = MAX_EXCHANGES_PER_DOC if has_summary else count

        session_count = db.execute(
            "SELECT COUNT(*) as cnt FROM chat_summaries WHERE upload_id = ?",
            (upload_id,),
        ).fetchone()["cnt"]

        return {
            "qa_ready": bool(upload["qa_ready"]),
            "exchange_count": effective_count,
            "limit": MAX_EXCHANGES_PER_DOC,
            "remaining": max(0, MAX_EXCHANGES_PER_DOC - effective_count),
            "has_summary": has_summary,
            "session_number": session_count + 1,
        }
    finally:
        db.close()


@router.get("/chat/summary/{upload_id}")
async def get_summary(upload_id: int, user: dict = Depends(get_current_user)):
    _verify_upload_ownership(upload_id, user["id"])
    db = get_db()
    try:
        rows = db.execute(
            "SELECT summary, session_number, created_at FROM chat_summaries "
            "WHERE upload_id = ? ORDER BY session_number ASC",
            (upload_id,),
        ).fetchall()
        # Also check uploads.chat_summary for legacy data (before chat_summaries table existed)
        upload = db.execute(
            "SELECT chat_summary FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        if upload is None:
            raise HTTPException(status_code=404, detail="Upload not found")

        summaries = [
            {"summary": r["summary"], "session": r["session_number"], "created_at": r["created_at"]}
            for r in rows
        ]
        # If uploads.chat_summary exists but no chat_summaries rows, include it as session 1
        if not summaries and upload["chat_summary"]:
            summaries = [{"summary": upload["chat_summary"], "session": 1, "created_at": None}]

        return {"summaries": summaries}
    finally:
        db.close()


@router.post("/chat/new-session/{upload_id}")
async def new_session(upload_id: int, user: dict = Depends(get_current_user)):
    _verify_upload_ownership(upload_id, user["id"])
    db = get_db()
    try:
        row = db.execute(
            "SELECT chat_summary FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        if not row or not row["chat_summary"]:
            raise HTTPException(status_code=400, detail="No completed session to reset")
        db.execute(
            "UPDATE uploads SET chat_summary = NULL WHERE id = ?", (upload_id,)
        )
        db.commit()
        return {"status": "ok", "remaining": MAX_EXCHANGES_PER_DOC}
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

            # Greetings don't count as an exchange
            if _is_greeting(question):
                name = _get_user_name(user["id"])
                greeting_reply = _get_greeting_reply(question, name)
                await ws.send_text(json.dumps({"type": "stream_start", "sources": []}))
                await ws.send_text(json.dumps({"type": "token", "content": greeting_reply}))
                db = get_db()
                try:
                    cnt = db.execute(
                        "SELECT COUNT(*) as cnt FROM chat_history WHERE upload_id = ?",
                        (upload_id,),
                    ).fetchone()["cnt"]
                finally:
                    db.close()
                await ws.send_text(json.dumps({
                    "type": "stream_end",
                    "exchange_count": cnt,
                    "limit": MAX_EXCHANGES_PER_DOC,
                    "summary": None,
                }))
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

            # Retrieve chunks (enrich vague follow-ups with prior context)
            prefs = _get_user_preferences(user["id"])
            prior = _get_recent_exchanges(upload_id)
            search_query = _enrich_query(question, prior)

            try:
                chunks = await retrieve_chunks(search_query, upload_id)
            except Exception as e:
                await ws.send_text(json.dumps({"type": "error", "detail": str(e)}))
                continue

            if not chunks:
                await ws.send_text(json.dumps({"type": "error", "detail": "No relevant content found"}))
                continue

            prompt = _build_chat_prompt(question, chunks, prefs, prior_exchanges=prior)
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

            new_count = count + 1
            summary = None
            if new_count >= MAX_EXCHANGES_PER_DOC:
                await ws.send_text(json.dumps({"type": "generating_summary"}))
                try:
                    summary = await _generate_summary(upload_id)
                except Exception as e:
                    log.error(f"Summary generation failed for upload {upload_id}: {e}")

            await ws.send_text(json.dumps({
                "type": "stream_end",
                "exchange_count": new_count,
                "limit": MAX_EXCHANGES_PER_DOC,
                "summary": summary,
            }))

    except WebSocketDisconnect:
        pass
