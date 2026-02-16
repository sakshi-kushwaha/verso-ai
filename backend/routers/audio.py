import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from tts.engine import generate_audio

router = APIRouter(tags=["audio"])

# Stub: maps reel_id -> text. Sakshi will replace with SQLite lookup.
_reel_text_stub: dict[int, str] = {}


def get_reel_text(reel_id: int) -> str | None:
    return _reel_text_stub.get(reel_id)


@router.get("/audio/{reel_id}")
async def serve_audio(reel_id: int):
    text = get_reel_text(reel_id)
    if text is None:
        raise HTTPException(status_code=404, detail="Reel not found")

    try:
        path = await asyncio.to_thread(generate_audio, text)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return FileResponse(
        path=str(path),
        media_type="audio/wav",
        filename=f"reel_{reel_id}.wav",
    )
