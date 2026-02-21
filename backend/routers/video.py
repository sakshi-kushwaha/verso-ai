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


def _create_overlay_png(width: int, height: int, title: str, summary: str,
                        category: str, out_path: str):
    """Create a transparent PNG overlay with gradient + text matching the feed UI."""
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    margin = int(width * 0.04)
    max_text_w = width - margin * 2
    bottom_pad = int(height * 0.04)

    # Prepare fonts
    cat_font = _resolve_font(int(height * 0.018))
    title_font = _resolve_font(int(height * 0.026))
    summary_font = _resolve_font(int(height * 0.016))

    # Prepare text
    cat_text = (category or "General").upper()
    cat_bbox = cat_font.getbbox(cat_text)
    cat_w = cat_bbox[2] - cat_bbox[0]
    cat_h = cat_bbox[3] - cat_bbox[1]
    tag_pad_x, tag_pad_y = 12, 5

    title_lines = _wrap_text(title or "", title_font, max_text_w)[:2]
    title_line_h = int(height * 0.030)

    summary_text = (summary or "")[:160]
    if len(summary or "") > 160:
        summary_text += "..."
    summary_lines = _wrap_text(summary_text, summary_font, max_text_w)[:3]
    summary_line_h = int(height * 0.022)

    # Calculate total text block height (bottom-up layout)
    gap_tag_title = int(height * 0.012)
    gap_title_summary = int(height * 0.006)

    tag_block_h = cat_h + tag_pad_y * 2
    title_block_h = len(title_lines) * title_line_h
    summary_block_h = len(summary_lines) * summary_line_h
    total_h = tag_block_h + gap_tag_title + title_block_h + gap_title_summary + summary_block_h

    # Position text block so it ends at bottom_pad from bottom edge
    block_top = height - bottom_pad - total_h

    # Smooth gradient — starts well above the text block
    gradient_top = max(0, block_top - int(height * 0.15))
    for y in range(gradient_top, height):
        progress = (y - gradient_top) / (height - gradient_top)
        alpha = int(210 * progress)
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

    # Draw category tag pill
    tag_y = block_top
    draw.rounded_rectangle(
        [margin, tag_y, margin + cat_w + tag_pad_x * 2, tag_y + tag_block_h],
        radius=8, fill=(99, 102, 241, 200),
    )
    draw.text((margin + tag_pad_x, tag_y + tag_pad_y), cat_text, font=cat_font, fill=(255, 255, 255))

    # Draw title
    title_y = tag_y + tag_block_h + gap_tag_title
    for line in title_lines:
        draw.text((margin, title_y), line, font=title_font, fill=(255, 255, 255))
        title_y += title_line_h

    # Draw summary
    summary_y = title_y + gap_title_summary
    for line in summary_lines:
        draw.text((margin, summary_y), line, font=summary_font, fill=(255, 255, 255, 180))
        summary_y += summary_line_h

    overlay.save(out_path, "PNG")


def _burn_text_into_video(source_path: str, out_path: str,
                          title: str, summary: str, category: str) -> bool:
    """Re-encode video with Pillow-rendered overlay (gradient + text) composited via ffmpeg."""
    try:
        # Get video dimensions with ffprobe
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
            _create_overlay_png(vid_w, vid_h, title, summary, category, overlay_path)

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
        log.error("Failed to burn text into video: %s", e)
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

    # Path is stored relative to cwd (e.g. "data/video_cache/reel_1.mp4") — use as-is

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
            "SELECT video_path, title, summary, category FROM reels WHERE id = ?", (reel_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row or not row["video_path"]:
        raise HTTPException(status_code=404, detail="Video not found for this reel")

    video_path = row["video_path"]

    if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
        raise HTTPException(status_code=404, detail="Video file missing")

    safe_title = re.sub(r'[^a-zA-Z0-9 ]', '', row["title"] or "reel").strip() or "reel"

    # Check for cached download with text overlay
    DOWNLOAD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    download_path = str(DOWNLOAD_CACHE_DIR / f"reel_{reel_id}.mp4")

    # Regenerate if download cache is missing or older than the source video
    stale = False
    if os.path.exists(download_path) and os.path.getsize(download_path) > 0:
        stale = os.path.getmtime(video_path) > os.path.getmtime(download_path)
    if not os.path.exists(download_path) or os.path.getsize(download_path) == 0 or stale:
        # Burn title, category, and summary into the video
        success = _burn_text_into_video(
            source_path=video_path,
            out_path=download_path,
            title=row["title"] or "",
            summary=row["summary"] or "",
            category=row["category"] or "General",
        )
        if not success:
            # Fallback: serve original video without text
            download_path = video_path

    return FileResponse(
        path=download_path,
        media_type="video/mp4",
        filename=f"{safe_title}.mp4",
        content_disposition_type="attachment",
    )
