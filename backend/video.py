"""Video reel composition using ffmpeg — stock video + TTS audio + background music.

Memory-conscious: uses 720p output and ffmpeg thread limits to stay under ~150MB per encode.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from config import VIDEO_CACHE_DIR

# Output dimensions — 720p vertical (saves ~60% RAM vs 1080p)
WIDTH = 720
HEIGHT = 1280

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

    if os.path.exists(out_path):
        return out_path

    tempo, pitch_st, bg_freq, bg_type = AUDIO_PROFILES.get(category or "", DEFAULT_PROFILE)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate category-specific background music
        bg_music_path = os.path.join(tmpdir, "bg_music.wav")
        _generate_background_music(bg_music_path, bg_freq, bg_type)

        # Build ffmpeg command
        inputs = ["-stream_loop", "-1", "-i", stock_video_path]
        filter_parts = []

        # Scale video to 720x1280 (saves RAM vs 1080x1920)
        filter_parts.append(
            f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
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
            "-crf", "30",            # slightly higher CRF = smaller files, less RAM
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            out_path,
        ]

        subprocess.run(cmd, check=True, capture_output=True, timeout=FFMPEG_ENCODE_TIMEOUT)

    return out_path
