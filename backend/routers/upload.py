import os
import json
import shutil
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, WebSocket, WebSocketDisconnect
from database import get_db
from pipeline import process_upload, TEMP_DIR
from auth import get_current_user
from ws_auth import ws_authenticate
from ws_manager import manager
from config import STALE_UPLOAD_MINUTES

router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _expire_stale_uploads(user_id: int):
    """Auto-mark uploads stuck in 'processing' for too long as failed or partial."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=STALE_UPLOAD_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    stale = conn.execute(
        "SELECT id FROM uploads WHERE user_id = ? AND status = 'processing' AND created_at < ?",
        (user_id, cutoff),
    ).fetchall()
    for row in stale:
        uid = row["id"]
        reel_count = conn.execute("SELECT COUNT(*) FROM reels WHERE upload_id = ?", (uid,)).fetchone()[0]
        if reel_count > 0:
            conn.execute(
                "UPDATE uploads SET status = 'partial', error_message = ? WHERE id = ?",
                (f"Generated {reel_count} reels before timeout. Partial reels are available.", uid),
            )
        else:
            conn.execute(
                "UPDATE uploads SET status = 'error', error_message = 'Processing timed out. Please try uploading again.' WHERE id = ?",
                (uid,),
            )
    conn.commit()
    conn.close()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    # Expire any stuck uploads before checking for active ones
    _expire_stale_uploads(user["id"])
    # Restrict to one upload at a time per user
    conn = get_db()
    active = conn.execute(
        "SELECT id FROM uploads WHERE user_id = ? AND status = 'processing'",
        (user["id"],),
    ).fetchone()
    conn.close()
    if active:
        raise HTTPException(409, "You already have a document being processed. Please wait for it to finish.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Only PDF and DOCX files are supported")

    os.makedirs(TEMP_DIR, exist_ok=True)
    temp_path = os.path.join(TEMP_DIR, file.filename)

    size = 0
    with open(temp_path, "wb") as f:
        while chunk := await file.read(8192):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                os.unlink(temp_path)
                raise HTTPException(400, "File exceeds 50 MB limit")
            f.write(chunk)

    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO uploads (user_id, filename, status, filepath) VALUES (?, ?, 'processing', ?)",
        (user["id"], file.filename, temp_path),
    )
    upload_id = cursor.lastrowid
    conn.commit()
    conn.close()

    process_upload(upload_id, temp_path, user["id"])

    return {"id": upload_id, "filename": file.filename, "status": "processing"}


@router.get("/uploads")
def list_uploads(user: dict = Depends(get_current_user)):
    _expire_stale_uploads(user["id"])
    conn = get_db()
    rows = conn.execute(
        """SELECT u.id, u.filename, u.status, u.doc_type, u.total_pages, u.qa_ready, u.created_at,
                  u.doc_summary,
                  (SELECT COUNT(*) FROM reels WHERE upload_id = u.id) AS reel_count,
                  (SELECT COUNT(*) FROM flashcards WHERE upload_id = u.id) AS flashcard_count
           FROM uploads u
           WHERE u.user_id = ?
           ORDER BY u.created_at DESC""",
        (user["id"],),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/upload/status/{upload_id}")
def get_upload_status(upload_id: int, user: dict = Depends(get_current_user)):
    _expire_stale_uploads(user["id"])
    conn = get_db()
    row = conn.execute("SELECT * FROM uploads WHERE id = ? AND user_id = ?", (upload_id, user["id"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Upload not found")

    reels_count = conn.execute(
        "SELECT COUNT(*) FROM reels WHERE upload_id = ?", (upload_id,)
    ).fetchone()[0]

    conn.close()

    return {
        "id": row["id"],
        "filename": row["filename"],
        "status": row["status"],
        "doc_type": row["doc_type"],
        "total_pages": row["total_pages"],
        "progress": row["progress"] if "progress" in row.keys() else 0,
        "stage": row["stage"] if "stage" in row.keys() else "uploading",
        "reels_generated": reels_count,
        "qa_ready": bool(row["qa_ready"]),
        "error_message": row["error_message"] if "error_message" in row.keys() else None,
    }


@router.get("/upload/{upload_id}/summary")
def get_or_generate_summary(upload_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    row = conn.execute(
        "SELECT doc_summary FROM uploads WHERE id = ? AND user_id = ?",
        (upload_id, user["id"]),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, "Upload not found")

    if row["doc_summary"]:
        return {"summary": row["doc_summary"], "generated": False}

    # On-demand generation for legacy books — try source_text first, fall back to reel summaries
    conn = get_db()
    reel_rows = conn.execute(
        "SELECT source_text, summary, narration FROM reels WHERE upload_id = ? ORDER BY id LIMIT 10",
        (upload_id,),
    ).fetchall()
    conn.close()

    if not reel_rows:
        raise HTTPException(404, "No content available to generate summary")

    # Prefer source_text, fall back to summary + narration from reels
    source_texts = [r["source_text"] for r in reel_rows if r["source_text"]]
    if source_texts:
        combined_text = "\n\n".join(source_texts)[:6000]
    else:
        parts = []
        for r in reel_rows:
            parts.append(r["summary"] or "")
            if r["narration"]:
                parts.append(r["narration"])
        combined_text = "\n\n".join(p for p in parts if p)[:6000]

    if not combined_text.strip():
        raise HTTPException(404, "No content available to generate summary")

    from llm import generate_doc_summary
    summary = generate_doc_summary(combined_text)
    if not summary:
        raise HTTPException(503, "Summary generation failed. Please try again.")

    conn = get_db()
    conn.execute("UPDATE uploads SET doc_summary = ? WHERE id = ?", (summary, upload_id))
    conn.commit()
    conn.close()

    return {"summary": summary, "generated": True}


@router.delete("/upload/{upload_id}")
def delete_upload(upload_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM uploads WHERE id = ? AND user_id = ?", (upload_id, user["id"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Upload not found")

    # Get reel IDs for bookmark + video cleanup
    reel_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM reels WHERE upload_id = ?", (upload_id,)
    ).fetchall()]

    # Delete related data (order matters for foreign key references)
    if reel_ids:
        placeholders = ",".join("?" * len(reel_ids))
        conn.execute(f"DELETE FROM bookmarks WHERE reel_id IN ({placeholders})", reel_ids)
    conn.execute("DELETE FROM bookmarks WHERE flashcard_id IN (SELECT id FROM flashcards WHERE upload_id = ?)", (upload_id,))
    conn.execute("DELETE FROM flashcards WHERE upload_id = ?", (upload_id,))
    conn.execute("DELETE FROM reels WHERE upload_id = ?", (upload_id,))
    conn.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
    conn.commit()
    conn.close()

    # Clean up cached video files
    from config import VIDEO_CACHE_DIR
    for reel_id in reel_ids:
        video_file = VIDEO_CACHE_DIR / f"reel_{reel_id}.mp4"
        if video_file.exists():
            try:
                video_file.unlink()
            except OSError:
                pass

    return {"message": "Document deleted"}


@router.websocket("/ws/upload/{upload_id}")
async def ws_upload_progress(ws: WebSocket, upload_id: int):
    await ws.accept()
    user = await ws_authenticate(ws)
    if user is None:
        return

    # Verify upload ownership
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM uploads WHERE id = ? AND user_id = ?", (upload_id, user["id"])
    ).fetchone()
    conn.close()
    if not row:
        await ws.close(code=1008, reason="Upload not found")
        return

    await manager.subscribe_upload(upload_id, ws)
    try:
        # Keep connection alive — client doesn't send data, just receives
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.unsubscribe_upload(upload_id, ws)
