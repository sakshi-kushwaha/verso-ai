import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from tts.engine import generate_audio
from database import get_db

router = APIRouter(tags=["audio"])


@router.get("/audio/summary/{upload_id}")
async def serve_summary_audio(upload_id: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT doc_summary FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row or not row["doc_summary"]:
        raise HTTPException(status_code=404, detail="Summary not found for this upload")

    try:
        path = await asyncio.to_thread(generate_audio, row["doc_summary"], reel_index=0)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return FileResponse(
        path=str(path),
        media_type="audio/wav",
        filename=f"summary_{upload_id}.wav",
    )


def get_reel_text(reel_id: int) -> str | None:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(narration, summary) AS text FROM reels WHERE id = ?", (reel_id,)
        ).fetchone()
        return row["text"] if row else None
    finally:
        conn.close()


@router.get("/audio/{reel_id}")
async def serve_audio(reel_id: int):
    text = get_reel_text(reel_id)
    if text is None:
        raise HTTPException(status_code=404, detail="Reel not found")

    try:
        path = await asyncio.to_thread(generate_audio, text, reel_index=reel_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return FileResponse(
        path=str(path),
        media_type="audio/wav",
        filename=f"reel_{reel_id}.wav",
    )
