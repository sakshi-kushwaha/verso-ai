import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from database import get_db
from config import VIDEO_CACHE_DIR

router = APIRouter(tags=["video"])


@router.get("/video/{reel_id}")
def serve_video(reel_id: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT video_path FROM reels WHERE id = ?", (reel_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row or not row["video_path"]:
        raise HTTPException(status_code=404, detail="Video not found for this reel")

    video_path = row["video_path"]

    # Path is stored relative to cwd (e.g. "data/video_cache/reel_1.mp4") — use as-is

    if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
        raise HTTPException(status_code=404, detail="Video file missing")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"reel_{reel_id}.mp4",
    )
