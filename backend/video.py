"""Video reel composition using ffmpeg — stock video + TTS audio + background music.

Memory-conscious: uses 720p output and ffmpeg thread limits to stay under ~150MB per encode.
"""

import csv
import os
import subprocess
import tempfile
from pathlib import Path

from config import VIDEO_CACHE_DIR, STOCK_VIDEOS_DIR

# Output dimensions — 1080p vertical
WIDTH = 1080
HEIGHT = 1920

# Per-category audio profiles: (tts_tempo, tts_pitch_semitones, bg_freq, bg_type)
AUDIO_PROFILES = {
    "Science":     (1.05, 1.0,  220, "sine"),
    "Biology":     (0.95, -0.5, 330, "sine"),
    "Astronomy":   (1.0,  0.5,  165, "sine"),
    "Mathematics": (1.1,  1.5,  440, "sine"),
    "History":     (0.9,  -1.0, 196, "sine"),
}
DEFAULT_PROFILE = (1.0, 0.0, 261, "sine")

# ffmpeg resource limits for 8GB environments
FFMPEG_THREADS = "2"          # limit encoder threads (default would use all cores)
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


# Transition types cycled across xfade joins
_XFADE_TRANSITIONS = ["fade", "fadeblack", "dissolve", "wipeleft", "slideup", "smoothleft"]


def _resolve_font() -> str:
    """Find a usable font path for drawtext overlays."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux (Docker)
        "/System/Library/Fonts/Helvetica.ttc",                    # macOS
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return "Sans"


def _generate_background_music(out_path: str, freq: float, wave_type: str, duration: float = 16.0):
    """Generate a soft ambient background tone using ffmpeg synthesis."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"{wave_type}=frequency={freq}:duration={duration}",
        "-f", "lavfi",
        "-i", f"{wave_type}=frequency={freq * 1.5}:duration={duration}",
        "-filter_complex",
        "[0:a]volume=0.03[a1];"
        "[1:a]volume=0.02[a2];"
        "[a1][a2]amix=inputs=2:duration=longest,"
        "afade=t=in:st=0:d=2,afade=t=out:st=13:d=3[out]",
        "-map", "[out]",
        "-threads", FFMPEG_THREADS,
        "-c:a", "pcm_s16le",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=30)


def compose_reel_video(
    reel_id: int,
    title: str,
    summary: str,
    stock_video_path: str,
    sound_effect_path: str | None = None,
    tts_audio_path: str | None = None,
    category: str | None = None,
) -> str:
    """Compose a video reel: stock video + pitch/tempo-shifted TTS + background music → MP4.

    Memory budget: ~100-150MB per encode at 720x1280 with 2 threads.
    Returns the path to the output MP4 file.
    """
    VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = str(VIDEO_CACHE_DIR / f"reel_{reel_id}.mp4")

    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    tempo, pitch_st, bg_freq, bg_type = AUDIO_PROFILES.get(category or "", DEFAULT_PROFILE)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate category-specific background music
        bg_music_path = os.path.join(tmpdir, "bg_music.wav")
        _generate_background_music(bg_music_path, bg_freq, bg_type)

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

        # TTS narration with per-category pitch/tempo shift
        if tts_audio_path and os.path.exists(tts_audio_path):
            inputs.extend(["-i", tts_audio_path])
            tts_filter = f"[{audio_idx}:a]atempo={tempo}"
            if pitch_st != 0.0:
                pitch_ratio = 2 ** (pitch_st / 12.0)
                tts_filter += f",asetrate=44100*{pitch_ratio:.4f},aresample=44100"
            tts_filter += ",volume=1.0[tts]"
            filter_parts.append(tts_filter)
            audio_layers.append("[tts]")
            audio_idx += 1

        # Sound effect (chime etc.)
        if sound_effect_path and os.path.exists(sound_effect_path):
            inputs.extend(["-i", sound_effect_path])
            filter_parts.append(f"[{audio_idx}:a]volume=0.2[sfx]")
            audio_layers.append("[sfx]")
            audio_idx += 1

        # Background music (always present)
        inputs.extend(["-i", bg_music_path])
        filter_parts.append(f"[{audio_idx}:a]volume=0.08[bgm]")
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
            "-t", "15",
            "-threads", FFMPEG_THREADS,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "26",            # slightly higher CRF = smaller files, less RAM
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
    """Compose a multi-clip video reel with transitions and text overlays.

    Each segment specifies a clip filename, overlay text, and duration.
    Clips are joined with xfade transitions, text overlays are drawn per segment,
    and audio (TTS + background music) is mixed on top.

    Memory budget: ~120-170MB per encode at 720x1280 with 2 threads.
    Returns the path to the output MP4 file.
    """
    VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = str(VIDEO_CACHE_DIR / f"reel_{reel_id}.mp4")

    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path

    n = len(segments)
    TRANSITION_DUR = 0.5
    TOTAL_DURATION = 15.0
    font = _resolve_font()

    # Scale segment durations so output = 15s accounting for xfade overlaps
    # Each xfade eats TRANSITION_DUR from total, so raw clip sum must be longer
    raw_durations = [s["duration"] for s in segments]
    raw_sum = sum(raw_durations)
    # Target raw sum = TOTAL_DURATION + (n-1) * TRANSITION_DUR
    target_raw = TOTAL_DURATION + (n - 1) * TRANSITION_DUR
    scale = target_raw / raw_sum if raw_sum > 0 else 1.0
    durations = [max(2.0, d * scale) for d in raw_durations]
    # Re-normalize after clamping
    actual_sum = sum(durations)
    if abs(actual_sum - target_raw) > 0.1:
        adjust = target_raw / actual_sum
        durations = [d * adjust for d in durations]

    tempo, pitch_st, bg_freq, bg_type = AUDIO_PROFILES.get(category or "", DEFAULT_PROFILE)

    catalog = load_video_catalog()
    cat_clips = catalog.get(category, catalog.get("general", []))
    clip_map = {c["file"]: c["path"] for c in cat_clips}

    with tempfile.TemporaryDirectory() as tmpdir:
        # Build ffmpeg inputs — each clip looped and trimmed to its duration
        inputs = []
        for i, seg in enumerate(segments):
            clip_path = clip_map.get(seg["clip"])
            if not clip_path or not os.path.exists(clip_path):
                raise FileNotFoundError(f"Clip not found: {seg['clip']}")
            inputs.extend(["-stream_loop", "-1", "-t", f"{durations[i]:.2f}", "-i", clip_path])

        filter_parts = []

        # Scale each clip to 720x1280
        for i in range(n):
            filter_parts.append(
                f"[{i}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={WIDTH}:{HEIGHT},setsar=1,setpts=PTS-STARTPTS[v{i}]"
            )

        # Chain xfade transitions
        # offset[i] = sum(durations[0..i]) - (i+1)*TRANSITION_DUR
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

        # Text overlays — title at top for first 3s, per-segment overlay at bottom
        drawtext_filters = []
        font_escaped = font.replace(":", "\\:")
        # Title overlay
        drawtext_filters.append(
            f"drawtext=fontfile='{font_escaped}':text='{_escape_drawtext(title)}':"
            f"fontsize=36:fontcolor=white:shadowcolor=black:shadowx=2:shadowy=2:"
            f"x=(w-text_w)/2:y=80:enable='between(t,0,3)'"
        )

        # Per-segment overlays
        seg_start = 0.0
        for i, seg in enumerate(segments):
            seg_end = seg_start + durations[i] - (TRANSITION_DUR if i < n - 1 else 0)
            overlay_text = seg.get("overlay", "")
            if overlay_text:
                drawtext_filters.append(
                    f"drawtext=fontfile='{font_escaped}':text='{_escape_drawtext(overlay_text)}':"
                    f"fontsize=30:fontcolor=white:shadowcolor=black:shadowx=2:shadowy=2:"
                    f"x=(w-text_w)/2:y=h-120:enable='between(t,{seg_start:.2f},{seg_end:.2f})'"
                )
            seg_start = seg_end

        if drawtext_filters:
            filter_parts.append(f"[{last_label}]{','.join(drawtext_filters)}[vout]")
        else:
            filter_parts.append(f"[{last_label}]null[vout]")

        # Audio pipeline — same as single-clip
        audio_layers = []
        audio_idx = n  # video inputs used indices 0..n-1

        # TTS narration with per-category pitch/tempo shift
        if tts_audio_path and os.path.exists(tts_audio_path):
            inputs.extend(["-i", tts_audio_path])
            tts_filter = f"[{audio_idx}:a]atempo={tempo}"
            if pitch_st != 0.0:
                pitch_ratio = 2 ** (pitch_st / 12.0)
                tts_filter += f",asetrate=44100*{pitch_ratio:.4f},aresample=44100"
            tts_filter += ",volume=1.0[tts]"
            filter_parts.append(tts_filter)
            audio_layers.append("[tts]")
            audio_idx += 1

        # Sound effect
        if sound_effect_path and os.path.exists(sound_effect_path):
            inputs.extend(["-i", sound_effect_path])
            filter_parts.append(f"[{audio_idx}:a]volume=0.2[sfx]")
            audio_layers.append("[sfx]")
            audio_idx += 1

        # Background music
        bg_music_path = os.path.join(tmpdir, "bg_music.wav")
        _generate_background_music(bg_music_path, bg_freq, bg_type)
        inputs.extend(["-i", bg_music_path])
        filter_parts.append(f"[{audio_idx}:a]volume=0.08[bgm]")
        audio_layers.append("[bgm]")
        audio_idx += 1

        # Mix audio
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
            "-preset", "fast",
            "-crf", "26",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            out_path,
        ]

        subprocess.run(cmd, check=True, capture_output=True, timeout=FFMPEG_ENCODE_TIMEOUT)

    return out_path


def _escape_drawtext(text: str) -> str:
    """Escape special characters for ffmpeg drawtext filter."""
    # Must escape: ' \ : %
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\u2019")  # Replace apostrophe with unicode right single quote
    text = text.replace(":", "\\:")
    text = text.replace("%", "%%")
    return text
