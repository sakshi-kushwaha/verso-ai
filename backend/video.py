"""Video reel composition using ffmpeg — stock video + TTS audio + background music.

Memory-conscious: uses 1080p output and ffmpeg thread limits to stay under ~400MB per encode.
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import VIDEO_CACHE_DIR, STOCK_VIDEOS_DIR

# Output dimensions — 1080p vertical
WIDTH = 1080
HEIGHT = 1920

# Duration bounds (seconds) — video length adapts to narration
MIN_DURATION = 10
MAX_DURATION = 60
DEFAULT_DURATION = 15

# Per-category ambient music: (base_freq, wave_type)
AUDIO_PROFILES = {
    "Science":     (220, "sine"),
    "Biology":     (330, "sine"),
    "Astronomy":   (165, "sine"),
    "Mathematics": (440, "sine"),
    "History":     (196, "sine"),
}
DEFAULT_PROFILE = (261, "sine")

# ffmpeg resource limits for 8GB environments
FFMPEG_THREADS = "4"          # limit encoder threads (default would use all cores)
FFMPEG_ENCODE_TIMEOUT = 180   # seconds

# Module-level video catalog cache
_video_catalog: dict | None = None


def load_video_catalog() -> dict[str, list[dict]]:
    """Parse data/videos.csv into {category: [{file, path, description}]} dict. Cached."""
    global _video_catalog
    if _video_catalog is not None:
        return _video_catalog

    catalog: dict[str, list[dict]] = {}
    csv_path = Path(__file__).parent / "data" / "videos.csv"
    if not csv_path.exists():
        _video_catalog = {}
        return _video_catalog

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_file = row.get("video_file", "").strip()
            description = row.get("description", "").strip()
            if not video_file:
                continue
            parts = video_file.split("/", 1)
            if len(parts) != 2:
                continue
            category, filename = parts
            full_path = str(STOCK_VIDEOS_DIR / video_file)
            catalog.setdefault(category, []).append({
                "file": filename,
                "path": full_path,
                "description": description,
            })

    _video_catalog = catalog
    return _video_catalog


def get_clips_for_category(category: str) -> list[dict]:
    """Return clips for a category, falling back to 'general'."""
    catalog = load_video_catalog()
    clips = catalog.get(category, [])
    if not clips:
        clips = catalog.get("general", [])
    return clips


# ---------------------------------------------------------------------------
# Image segment helpers
# ---------------------------------------------------------------------------

_BG_IMAGES_DIR = Path(__file__).parent / "static" / "bg-images"


def get_images_for_category(category: str) -> list[dict]:
    """Return background images for a category, falling back to 'general'."""
    folder = _BG_IMAGES_DIR / category
    if not folder.is_dir():
        folder = _BG_IMAGES_DIR / "general"
    if not folder.is_dir():
        return []
    return [
        {"file": f.name, "path": str(f)}
        for f in sorted(folder.iterdir())
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    ]


def _resolve_pillow_font(size: int = 48, font_path: str | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a specific font or fall back to a usable system font."""
    if font_path and os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    # Fallback chain
    fallbacks = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in fallbacks:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
               max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = font.getbbox(test)
        if bbox[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _prepare_image_segment(image_path: str, text: str, width: int, height: int,
                           tmpdir: str, index: int = 0) -> str:
    """Compose text onto an image using Pillow.

    Opens the image, crops/resizes to width x height, draws a semi-transparent
    dark gradient bar at the bottom, and renders white text on it.
    Returns path to the composited image in tmpdir.
    """
    img = Image.open(image_path).convert("RGB")

    # Resize to cover then center-crop
    img_ratio = img.width / img.height
    target_ratio = width / height
    if img_ratio > target_ratio:
        new_h = height
        new_w = int(height * img_ratio)
    else:
        new_w = width
        new_h = int(width / img_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - width) // 2
    top = (new_h - height) // 2
    img = img.crop((left, top, left + width, top + height))

    if text:
        # Draw dark gradient overlay at bottom 30% of image
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        gradient_top = int(height * 0.55)
        for y in range(gradient_top, height):
            alpha = int(180 * (y - gradient_top) / (height - gradient_top))
            draw_overlay.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)
        img = img.convert("RGB")

        # Draw text
        draw = ImageDraw.Draw(img)
        font_large = _resolve_pillow_font(56)
        margin = 60
        max_text_width = width - margin * 2
        lines = _wrap_text(text, font_large, max_text_width)

        # Position text in the gradient area
        line_height = 70
        total_text_height = len(lines) * line_height
        text_y = int(height * 0.72) - total_text_height // 2

        for line in lines:
            bbox = font_large.getbbox(line)
            text_w = bbox[2] - bbox[0]
            text_x = (width - text_w) // 2
            # Shadow
            draw.text((text_x + 2, text_y + 2), line, font=font_large, fill=(0, 0, 0, 200))
            # Main text
            draw.text((text_x, text_y), line, font=font_large, fill=(255, 255, 255))
            text_y += line_height

    out = os.path.join(tmpdir, f"img_seg_{index}.jpg")
    img.save(out, "JPEG", quality=92)
    return out


# ---------------------------------------------------------------------------
# Text style presets — each reel gets a unique look (font, color, effects)
# like different Instagram creators. Rotated by reel_id.
# ---------------------------------------------------------------------------
_TEXT_STYLES = [
    {   # Clean bold sans — Instagram reel style
        "font": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "font_linux": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "font_size": 48, "uppercase": False, "stroke_w": 3,
    },
]


def _create_word_group_png(text: str, width: int, height: int,
                            tmpdir: str, index: int = 0,
                            style_idx: int = 0) -> str:
    """Create a transparent PNG with multi-line white text + black stroke.

    Instagram reel style: bold white text with tight stroke, centered,
    positioned in the lower third. Wraps to multiple lines automatically.
    """
    style = _TEXT_STYLES[style_idx % len(_TEXT_STYLES)]
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_path = style.get("font", "")
    if not font_path or not os.path.exists(font_path):
        font_path = style.get("font_linux", "")
    font = _resolve_pillow_font(style["font_size"], font_path=font_path)

    margin = 100  # wide margins so text never touches edges
    max_text_width = width - margin * 2
    display = text.upper() if style["uppercase"] else text
    lines = _wrap_text(display, font, max_text_width)

    line_height = style["font_size"] + 14
    total_text_height = len(lines) * line_height
    # Lower third — ~70% down the frame
    text_y_start = int(height * 0.70) - total_text_height // 2

    stroke_w = style.get("stroke_w", 4)

    # White text with black stroke — clean Instagram look
    text_y = text_y_start
    for line in lines:
        bbox = font.getbbox(line)
        text_w = bbox[2] - bbox[0]
        text_x = (width - text_w) // 2
        draw.text((text_x, text_y), line, font=font,
                  fill=(255, 255, 255, 255),
                  stroke_width=stroke_w, stroke_fill=(0, 0, 0, 220))
        text_y += line_height

    out = os.path.join(tmpdir, f"wordgroup_{index}.png")
    img.save(out, "PNG")
    return out


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = round((seconds % 1) * 100)
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ---------------------------------------------------------------------------
# Caption style presets — each reel gets a different look (rotated by reel_id)
# ---------------------------------------------------------------------------
_CAPTION_STYLES = [
    {   # Style 0: Clean Pop — white text, subtle pop-in
        "font_name": "DejaVu Sans",
        "font_size": 50, "bold": -1,
        "primary": "&H00FFFFFF",   # white
        "outline": "&H00000000",   # black
        "shadow_color": "&H80000000",
        "outline_px": 3, "shadow_px": 0, "spacing": 1,
        "anim": r"{\fad(150,100)\t(0,120,\fscx105\fscy105)\t(120,250,\fscx100\fscy100)}",
    },
    {   # Style 1: Bold Bounce — thicker outline + shadow, bouncy entrance
        "font_name": "DejaVu Sans",
        "font_size": 52, "bold": -1,
        "primary": "&H00FFFFFF",
        "outline": "&H00000000",
        "shadow_color": "&H90000000",
        "outline_px": 5, "shadow_px": 2, "spacing": 0,
        "anim": r"{\fad(100,120)\t(0,100,\fscx118\fscy118)\t(100,180,\fscx96\fscy96)\t(180,280,\fscx100\fscy100)}",
    },
    {   # Style 2: Editorial — white serif, gentle scale
        "font_name": "DejaVu Serif",
        "font_size": 48, "bold": -1,
        "primary": "&H00FFFFFF",
        "outline": "&H00000000",
        "shadow_color": "&H80000000",
        "outline_px": 3, "shadow_px": 1, "spacing": 2,
        "anim": r"{\fad(200,150)\t(0,200,\fscx103\fscy103)\t(200,350,\fscx100\fscy100)}",
    },
    {   # Style 3: Mono Tech — white monospace, quick snap-in
        "font_name": "DejaVu Sans Mono",
        "font_size": 44, "bold": -1,
        "primary": "&H00FFFFFF",
        "outline": "&H00000000",
        "shadow_color": "&HA0000000",
        "outline_px": 2, "shadow_px": 2, "spacing": 1,
        "anim": r"{\fad(80,80)}",
    },
]


def _create_ass_captions(narration: str, tts_duration: float, filepath: str,
                          width: int = 1080, height: int = 1920,
                          style_idx: int = 0) -> str | None:
    """Create ASS subtitle file with animated captions.

    tts_duration should be the *actual* TTS audio length (not the padded video
    duration) so captions stay in sync with spoken words.
    Each word group gets fade/scale animation. Style rotates per reel
    so every reel looks visually distinct — like different Instagram creators.
    """
    clean = re.sub(r'\*+', '', narration).strip()
    words = clean.split()
    if not words:
        return None

    style = _CAPTION_STYLES[style_idx % len(_CAPTION_STYLES)]

    wpg = 7
    groups = [" ".join(words[i:i + wpg]) for i in range(0, len(words), wpg)]
    total_words = len(words)

    start_pad = 0.05
    usable = tts_duration - start_pad
    if usable < 1:
        usable, start_pad = tts_duration, 0
    tpw = usable / total_words

    # Build ASS style line from preset
    style_line = (
        f"Style: Caption,{style['font_name']},{style['font_size']},"
        f"{style['primary']},&H000000FF,{style['outline']},"
        f"{style['shadow_color']},{style['bold']},0,0,0,100,100,"
        f"{style['spacing']},0,1,{style['outline_px']},{style['shadow_px']},"
        f"5,80,80,0,1"
    )

    lines = [
        "[Script Info]",
        "Title: Reel Captions",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        style_line,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    w_offset = 0
    gap = 0.15  # 150ms gap between captions to prevent overlap
    anim = style["anim"]
    for grp in groups:
        gcnt = len(grp.split())
        t0 = start_pad + w_offset * tpw
        t1 = start_pad + (w_offset + gcnt) * tpw - gap
        if t1 <= t0:
            t1 = t0 + 0.5
        start_ts = _seconds_to_ass_time(t0)
        end_ts = _seconds_to_ass_time(t1)

        text = grp.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        lines.append(f"Dialogue: 0,{start_ts},{end_ts},Caption,,0,0,0,,{anim}{text}")
        w_offset += gcnt

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return filepath


def _burn_word_sync(video_path: str, narration: str, duration: float,
                     tmpdir: str, reel_id: int = 0) -> str:
    """Second-pass: burn word-synced text onto composed video using Pillow PNGs.

    Each reel gets a different text style (rotated from _TEXT_STYLES) so every
    reel looks unique — like different Instagram creators.
    Returns path to the output video with text overlaid.
    """
    words = narration.split()
    if not words:
        return video_path

    words_per_group = 7
    groups = []
    for i in range(0, len(words), words_per_group):
        groups.append(" ".join(words[i:i + words_per_group]))

    if not groups:
        return video_path

    # Pick a style for this reel (rotate through styles)
    style_idx = reel_id % len(_TEXT_STYLES)

    # Calculate timing
    total_words = len(words)
    start_pad = 0.3
    end_pad = 0.5
    usable = duration - start_pad - end_pad
    if usable < 1:
        usable = duration
        start_pad = 0
    time_per_word = usable / total_words

    # Generate PNGs and build overlay filter chain
    inputs = ["-i", video_path]
    filter_parts = []
    current_label = "0:v"
    word_offset = 0

    for idx, group in enumerate(groups):
        group_word_count = len(group.split())
        t_start = start_pad + word_offset * time_per_word
        t_end = start_pad + (word_offset + group_word_count) * time_per_word

        # Render PNG for this word group with the reel's style
        png_path = _create_word_group_png(group, WIDTH, HEIGHT, tmpdir, idx,
                                           style_idx=style_idx)
        input_idx = idx + 1  # input 0 is the video
        inputs.extend(["-i", png_path])

        out_label = f"wg{idx}"
        filter_parts.append(
            f"[{current_label}][{input_idx}:v]overlay=0:0"
            f":enable='between(t,{t_start:.3f},{t_end:.3f})'"
            f":format=auto[{out_label}]"
        )
        current_label = out_label
        word_offset += group_word_count

    filter_complex = ";".join(filter_parts)
    out = os.path.join(tmpdir, "reel_with_text.mp4")
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{current_label}]",
        "-map", "0:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
        "-c:a", "copy",
        "-threads", FFMPEG_THREADS,
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        out,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=FFMPEG_ENCODE_TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError(
            f"word-sync burn failed (rc={result.returncode}):\n"
            f"STDERR: {result.stderr.decode(errors='replace')[-2000:]}"
        )
    return out


# Transition types cycled across xfade joins
_XFADE_TRANSITIONS = ["fade", "fadeblack", "dissolve", "wipeleft", "slideup", "smoothleft"]


def _get_raw_audio_duration(audio_path: str | None) -> float | None:
    """Get raw audio duration in seconds via ffprobe. Returns None on failure."""
    if not audio_path or not os.path.exists(audio_path):
        return None
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "json", audio_path],
            capture_output=True, timeout=10,
        )
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])
    except Exception:
        return None


def _get_tts_duration(tts_audio_path: str | None) -> float:
    """Get TTS audio duration in seconds using ffprobe, clamped to bounds."""
    dur = _get_raw_audio_duration(tts_audio_path)
    if dur is None:
        return DEFAULT_DURATION
    # Add 1.5s padding after narration ends
    return max(MIN_DURATION, min(dur + 1.5, MAX_DURATION))


_bgm_cache: dict[str, str] = {}  # {cache_key: path} for reusing background music


def _generate_background_music(out_path: str, freq: float, wave_type: str, duration: float = 16.0):
    """Generate ambient background music — a warm pad with fade in/out. Cached per freq+duration."""
    from config import AUDIO_CACHE_DIR
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Round duration to nearest second for better cache hits
    dur_rounded = round(duration)
    cache_key = f"bgm_{int(freq)}_{wave_type}_{dur_rounded}"
    cached_path = str(AUDIO_CACHE_DIR / f"{cache_key}.wav")

    if os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
        # Copy cached file to the requested output path
        import shutil
        shutil.copy2(cached_path, out_path)
        return

    fade_out_start = max(0, duration - 3)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"{wave_type}=frequency={freq}:duration={duration}",
        "-f", "lavfi",
        "-i", f"{wave_type}=frequency={freq * 1.498}:duration={duration}",
        "-f", "lavfi",
        "-i", f"{wave_type}=frequency={freq * 0.501}:duration={duration}",
        "-filter_complex",
        f"[0:a]volume=0.06[a1];"
        f"[1:a]volume=0.04[a2];"
        f"[2:a]volume=0.03[a3];"
        f"[a1][a2][a3]amix=inputs=3:duration=longest:normalize=0,"
        f"lowpass=f=800,highpass=f=80,"
        f"afade=t=in:st=0:d=2,afade=t=out:st={fade_out_start:.1f}:d=3[out]",
        "-map", "[out]",
        "-threads", FFMPEG_THREADS,
        "-c:a", "pcm_s16le",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=30)

    # Cache the generated file for reuse
    try:
        import shutil
        shutil.copy2(out_path, cached_path)
    except Exception:
        pass


def compose_reel_video(
    reel_id: int,
    title: str,
    summary: str,
    stock_video_path: str,
    sound_effect_path: str | None = None,
    tts_audio_path: str | None = None,
    category: str | None = None,
) -> str:
    """Compose a video reel: stock video + TTS narration + background music → MP4.

    Video duration adapts to TTS narration length (10-30s).
    Memory budget: ~200-250MB per encode at 1080x1920 with 2 threads.
    Returns the path to the output MP4 file.
    """
    VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = str(VIDEO_CACHE_DIR / f"reel_{reel_id}.mp4")

    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    # Determine video duration from TTS audio length
    duration = _get_tts_duration(tts_audio_path)
    bg_freq, bg_type = AUDIO_PROFILES.get(category or "", DEFAULT_PROFILE)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate background music matching video duration
        bg_music_path = os.path.join(tmpdir, "bg_music.wav")
        _generate_background_music(bg_music_path, bg_freq, bg_type, duration=duration + 1)

        # Build ffmpeg command
        inputs = ["-stream_loop", "-1", "-i", stock_video_path]
        filter_parts = []

        # Scale video to 1080x1920 with lanczos for sharp upscaling
        filter_parts.append(
            f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={WIDTH}:{HEIGHT},setsar=1[vout]"
        )

        audio_layers = []
        audio_idx = 1

        # TTS narration
        if tts_audio_path and os.path.exists(tts_audio_path):
            inputs.extend(["-i", str(tts_audio_path)])
            filter_parts.append(f"[{audio_idx}:a]volume=1.2[tts]")
            audio_layers.append("[tts]")
            audio_idx += 1

        # Sound effect (chime etc.)
        if sound_effect_path and os.path.exists(sound_effect_path):
            inputs.extend(["-i", str(sound_effect_path)])
            filter_parts.append(f"[{audio_idx}:a]volume=0.25[sfx]")
            audio_layers.append("[sfx]")
            audio_idx += 1

        # Background music (always present, audible but below narration)
        inputs.extend(["-i", bg_music_path])
        filter_parts.append(f"[{audio_idx}:a]volume=0.15[bgm]")
        audio_layers.append("[bgm]")
        audio_idx += 1

        # Mix all audio layers
        if len(audio_layers) > 1:
            filter_parts.append(
                f"{''.join(audio_layers)}amix=inputs={len(audio_layers)}:duration=longest:normalize=0[aout]"
            )
            audio_map = ["-map", "[aout]"]
        elif len(audio_layers) == 1:
            audio_map = ["-map", audio_layers[0]]
        else:
            audio_map = ["-an"]

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            *audio_map,
            "-t", str(duration),
            "-threads", FFMPEG_THREADS,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "30",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            out_path,
        ]

        subprocess.run(cmd, check=True, capture_output=True, timeout=FFMPEG_ENCODE_TIMEOUT)

    return out_path


def compose_multi_clip_reel(
    reel_id: int,
    title: str,
    narration: str,
    segments: list[dict],
    category: str | None = None,
    tts_audio_path: str | None = None,
    sound_effect_path: str | None = None,
) -> str:
    """Compose a multi-clip video reel with transitions.

    Segments can be video clips or images (with text overlays via Pillow).
    Segment format:
        {"type": "video", "clip": "01.mp4", "duration": 3.0}
        {"type": "image", "image": "03.jpg", "image_path": "/abs/path", "text": "...", "duration": 3.0}

    Clips are joined with xfade transitions, audio (TTS + background music)
    is mixed on top. Image segments get a Ken Burns slow-zoom effect.

    Video duration adapts to TTS narration length (10-30s).
    Memory budget: ~200-300MB per encode at 1080x1920 with 2 threads.
    Returns the path to the output MP4 file.
    """
    VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = str(VIDEO_CACHE_DIR / f"reel_{reel_id}.mp4")

    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    n = len(segments)
    TRANSITION_DUR = 0.5
    FPS = 25
    TOTAL_DURATION = _get_tts_duration(tts_audio_path)

    # Scale segment durations so output matches TTS, accounting for xfade overlaps
    raw_durations = [s["duration"] for s in segments]
    raw_sum = sum(raw_durations)
    target_raw = TOTAL_DURATION + (n - 1) * TRANSITION_DUR
    scale = target_raw / raw_sum if raw_sum > 0 else 1.0
    durations = [max(2.0, d * scale) for d in raw_durations]
    actual_sum = sum(durations)
    if abs(actual_sum - target_raw) > 0.1:
        adjust = target_raw / actual_sum
        durations = [d * adjust for d in durations]

    bg_freq, bg_type = AUDIO_PROFILES.get(category or "", DEFAULT_PROFILE)

    # Build clip path lookup for video segments
    catalog = load_video_catalog()
    cat_clips = catalog.get(category, catalog.get("general", []))
    clip_map = {c["file"]: c["path"] for c in cat_clips}

    with tempfile.TemporaryDirectory() as tmpdir:
        # Build ffmpeg inputs — video clips or composited images
        inputs = []
        filter_parts = []

        for i, seg in enumerate(segments):
            seg_type = seg.get("type", "video")
            dur = durations[i]

            if seg_type == "image":
                # Prepare image with Pillow text overlay
                img_path = seg.get("image_path", "")
                if not img_path or not os.path.exists(img_path):
                    raise FileNotFoundError(f"Image not found: {seg.get('image', '')}")
                comp_path = _prepare_image_segment(
                    img_path, seg.get("text", ""), WIDTH, HEIGHT, tmpdir, index=i,
                )
                # Still image input: loop for duration
                inputs.extend(["-loop", "1", "-t", f"{dur:.2f}", "-i", comp_path])
                # Ken Burns slow zoom (1.0 → 1.08) on image segments
                num_frames = int(dur * FPS)
                filter_parts.append(
                    f"[{i}:v]zoompan=z='min(zoom+0.001,1.08)'"
                    f":d={num_frames}:s={WIDTH}x{HEIGHT}:fps={FPS},"
                    f"setpts=PTS-STARTPTS[v{i}]"
                )
            else:
                # Video clip input: loop and trim
                clip_path = clip_map.get(seg.get("clip", ""))
                if not clip_path or not os.path.exists(clip_path):
                    raise FileNotFoundError(f"Clip not found: {seg.get('clip', '')}")
                inputs.extend(["-r", str(FPS), "-stream_loop", "-1", "-t", f"{dur:.2f}", "-i", clip_path])
                filter_parts.append(
                    f"[{i}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase"
                    f":flags=lanczos,crop={WIDTH}:{HEIGHT},setsar=1[v{i}]"
                )

        next_input_idx = n  # video/image inputs used indices 0..n-1

        # Chain xfade transitions
        if n == 1:
            last_label = "v0"
        else:
            last_label = "v0"
            for i in range(n - 1):
                offset = sum(durations[:i + 1]) - (i + 1) * TRANSITION_DUR
                transition = _XFADE_TRANSITIONS[i % len(_XFADE_TRANSITIONS)]
                out_label = f"xf{i}"
                filter_parts.append(
                    f"[{last_label}][v{i + 1}]xfade=transition={transition}"
                    f":duration={TRANSITION_DUR}:offset={offset:.3f}[{out_label}]"
                )
                last_label = out_label

        # Animated narration captions (ASS subtitles — style rotates per reel)
        # Use actual TTS audio duration (not padded video duration) so captions
        # stay in sync with spoken narration.
        if narration:
            ass_path = os.path.join(tmpdir, "captions.ass")
            caption_style = reel_id % len(_CAPTION_STYLES)
            raw_tts_dur = _get_raw_audio_duration(tts_audio_path) or (TOTAL_DURATION - 1.5)
            if _create_ass_captions(narration, raw_tts_dur, ass_path, WIDTH, HEIGHT,
                                     style_idx=caption_style):
                ass_esc = ass_path.replace("\\", "/").replace(":", "\\:")
                filter_parts.append(
                    f"[{last_label}]ass={ass_esc}"
                    f":fontsdir=/usr/share/fonts/truetype/dejavu[vout_sub]"
                )
                last_label = "vout_sub"

        # Final video output label
        filter_parts.append(f"[{last_label}]null[vout]")

        # Audio pipeline
        audio_layers = []
        audio_idx = next_input_idx  # after video + word overlay inputs

        if tts_audio_path and os.path.exists(tts_audio_path):
            inputs.extend(["-i", str(tts_audio_path)])
            filter_parts.append(f"[{audio_idx}:a]volume=1.2[tts]")
            audio_layers.append("[tts]")
            audio_idx += 1

        if sound_effect_path and os.path.exists(sound_effect_path):
            inputs.extend(["-i", str(sound_effect_path)])
            filter_parts.append(f"[{audio_idx}:a]volume=0.25[sfx]")
            audio_layers.append("[sfx]")
            audio_idx += 1

        bg_music_path = os.path.join(tmpdir, "bg_music.wav")
        _generate_background_music(bg_music_path, bg_freq, bg_type, duration=TOTAL_DURATION + 1)
        inputs.extend(["-i", bg_music_path])
        filter_parts.append(f"[{audio_idx}:a]volume=0.15[bgm]")
        audio_layers.append("[bgm]")
        audio_idx += 1

        if len(audio_layers) > 1:
            filter_parts.append(
                f"{''.join(audio_layers)}amix=inputs={len(audio_layers)}:duration=longest:normalize=0[aout]"
            )
            audio_map = ["-map", "[aout]"]
        elif len(audio_layers) == 1:
            audio_map = ["-map", audio_layers[0]]
        else:
            audio_map = ["-an"]

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            *audio_map,
            "-t", str(TOTAL_DURATION),
            "-threads", FFMPEG_THREADS,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "30",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            out_path,
        ]

        subprocess.run(cmd, check=True, capture_output=True, timeout=FFMPEG_ENCODE_TIMEOUT)

    return out_path
