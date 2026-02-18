import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from tts.engine import generate_audio
from database import get_db

router = APIRouter(tags=["audio"])


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
