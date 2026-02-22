import logging
import os
import re
import subprocess
import tempfile
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw, ImageFont
from database import get_db
from config import VIDEO_CACHE_DIR

log = logging.getLogger(__name__)
router = APIRouter(tags=["video"])

DOWNLOAD_CACHE_DIR = VIDEO_CACHE_DIR / "downloads"
FFMPEG_THREADS = "2"


def _resolve_font(size: int = 48):
    """Find a usable font for Pillow text rendering."""
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(text, font, max_width):
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if font.getbbox(test)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _create_title_overlay(width: int, height: int, title: str, one_liner: str,
                          out_path: str):
    """Create a transparent PNG overlay with gradient + title + one-liner at bottom.

    Matches the feed UI layout — no category pill, no summary.
    """
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    margin = int(width * 0.04)
    max_text_w = width - margin * 2
    bottom_pad = int(height * 0.05)

    title_font = _resolve_font(int(height * 0.026))
    liner_font = _resolve_font(int(height * 0.016))

    title_lines = _wrap_text(title or "", title_font, max_text_w)[:2]
    title_line_h = int(height * 0.030)

    liner_lines = _wrap_text(one_liner or "", liner_font, max_text_w)[:2]
    liner_line_h = int(height * 0.022)

    gap = int(height * 0.008)
    title_block_h = len(title_lines) * title_line_h
    liner_block_h = len(liner_lines) * liner_line_h
    total_h = title_block_h + gap + liner_block_h

    block_top = height - bottom_pad - total_h

    # Smooth gradient — starts well above the text
    gradient_top = max(0, block_top - int(height * 0.12))
    for y in range(gradient_top, height):
        progress = (y - gradient_top) / (height - gradient_top)
        alpha = int(180 * progress)
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

    # Draw title
    title_y = block_top
    for line in title_lines:
        draw.text((margin, title_y), line, font=title_font, fill=(255, 255, 255))
        title_y += title_line_h

    # Draw one-liner
    liner_y = title_y + gap
    for line in liner_lines:
        draw.text((margin, liner_y), line, font=liner_font, fill=(255, 255, 255, 160))
        liner_y += liner_line_h

    overlay.save(out_path, "PNG")


def _burn_title_into_video(source_path: str, out_path: str,
                           title: str, one_liner: str) -> bool:
    """Re-encode video with title + one-liner overlay at bottom."""
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", source_path],
            capture_output=True, text=True, timeout=10,
        )
        parts = probe.stdout.strip().split(",")
        vid_w, vid_h = int(parts[0]), int(parts[1])
    except Exception:
        vid_w, vid_h = 1080, 1920

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            overlay_path = os.path.join(tmpdir, "overlay.png")
            _create_title_overlay(vid_w, vid_h, title, one_liner, overlay_path)

            cmd = [
                "ffmpeg", "-y",
                "-i", source_path,
                "-i", overlay_path,
                "-filter_complex", "[0:v][1:v]overlay=0:0",
                "-threads", FFMPEG_THREADS,
                "-c:v", "libx264", "-preset", "fast", "-crf", "26",
                "-profile:v", "baseline", "-level", "3.1",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                "-pix_fmt", "yuv420p",
                out_path,
            ]

            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            return True
    except Exception as e:
        log.error("Failed to burn title into video: %s", e)
        return False


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

    if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
        raise HTTPException(status_code=404, detail="Video file missing")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"reel_{reel_id}.mp4",
    )


@router.get("/video/{reel_id}/download")
def download_video(reel_id: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT video_path, title, one_liner FROM reels WHERE id = ?", (reel_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row or not row["video_path"]:
        raise HTTPException(status_code=404, detail="Video not found for this reel")

    video_path = row["video_path"]

    if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
        raise HTTPException(status_code=404, detail="Video file missing")

    safe_title = re.sub(r'[^a-zA-Z0-9 ]', '', row["title"] or "reel").strip() or "reel"

    # Build download with title + one-liner overlay
    DOWNLOAD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    download_path = str(DOWNLOAD_CACHE_DIR / f"reel_{reel_id}.mp4")

    # Always regenerate — source video or metadata may have changed
    success = _burn_title_into_video(
        source_path=video_path,
        out_path=download_path,
        title=row["title"] or "",
        one_liner=row["one_liner"] or "",
    )
    if not success:
        download_path = video_path

    return FileResponse(
        path=download_path,
        media_type="video/mp4",
        filename=f"{safe_title}.mp4",
        content_disposition_type="attachment",
    )
