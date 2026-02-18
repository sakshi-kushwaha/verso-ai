from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import subprocess
import threading
import wave
from pathlib import Path

from config import (
    AUDIO_CACHE_DIR,
    TTS_ENGINE,
    PIPER_MODEL_DIR,
    PIPER_MODEL,
    PIPER_MULTI_MODEL,
    ESPEAK_CMD,
    ESPEAK_VOICE,
    ESPEAK_SPEED,
    ESPEAK_PITCH,
    ESPEAK_GAP,
)

log = logging.getLogger(__name__)

_tts_lock = threading.Lock()
_piper_voice = None
_piper_multi_voice = None

# ---------------------------------------------------------------------------
# Edge-TTS voices — Microsoft Neural voices (near-human quality, free)
# Rotated across reels for variety
# ---------------------------------------------------------------------------
EDGE_VOICES = [
    "en-GB-SoniaNeural",       # warm British female — great for narration
    "en-US-AndrewMultilingualNeural",  # clear, calm male
    "en-GB-RyanNeural",        # friendly British male
    "en-US-AvaMultilingualNeural",     # natural, expressive female
]

# ---------------------------------------------------------------------------
# Piper fallback — curated speaker IDs from libritts_r-medium (904 speakers)
# ---------------------------------------------------------------------------
CURATED_SPEAKERS = [3, 14, 28, 45, 60, 92, 118, 175]

# Piper synthesis parameters — slower, more expressive
PIPER_LENGTH_SCALE = 1.15
PIPER_NOISE_SCALE = 0.7
PIPER_NOISE_W_SCALE = 0.9


def _content_hash(text: str, voice_key: str = "") -> str:
    key = text.strip().lower()
    if voice_key:
        key += f"|voice={voice_key}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def get_audio_path(text: str) -> Path | None:
    h = _content_hash(text)
    path = AUDIO_CACHE_DIR / f"{h}.wav"
    return path if path.exists() else None


# ---------------------------------------------------------------------------
# Edge-TTS (primary — near-human quality, requires internet)
# ---------------------------------------------------------------------------

def _generate_edge_tts(text: str, path: Path, voice: str) -> bool:
    """Generate audio with Microsoft Edge Neural TTS. Returns True on success."""
    try:
        import edge_tts

        mp3_path = path.with_suffix(".mp3")

        async def _run():
            communicate = edge_tts.Communicate(text, voice, rate="-5%")
            await communicate.save(str(mp3_path))

        asyncio.run(_run())

        # Convert MP3 to WAV for consistent pipeline (ffmpeg needs WAV)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp3_path), "-ar", "22050", "-ac", "1",
             "-c:a", "pcm_s16le", str(path)],
            capture_output=True, timeout=15, check=True,
        )
        mp3_path.unlink(missing_ok=True)
        return True
    except Exception as e:
        log.warning("Edge-TTS failed: %s", e)
        path.unlink(missing_ok=True)
        path.with_suffix(".mp3").unlink(missing_ok=True)
        return False


# ---------------------------------------------------------------------------
# Piper TTS (offline fallback — good quality, no internet needed)
# ---------------------------------------------------------------------------

def _load_piper_model(model_name: str):
    try:
        from piper import PiperVoice
        model_path = PIPER_MODEL_DIR / model_name
        config_path = PIPER_MODEL_DIR / f"{model_name}.json"
        if not model_path.exists():
            raise FileNotFoundError(f"Piper model not found: {model_path}")
        voice = PiperVoice.load(str(model_path), config_path=str(config_path))
        log.info("Piper TTS loaded: %s", model_name)
        return voice
    except Exception as e:
        log.warning("Piper model %s unavailable: %s", model_name, e)
        return None


def _get_piper_voice():
    global _piper_voice
    if _piper_voice is not None:
        return _piper_voice
    _piper_voice = _load_piper_model(PIPER_MODEL)
    return _piper_voice


def _get_piper_multi_voice():
    global _piper_multi_voice
    if _piper_multi_voice is not None:
        return _piper_multi_voice
    _piper_multi_voice = _load_piper_model(PIPER_MULTI_MODEL)
    return _piper_multi_voice


def _generate_piper(text: str, path: Path, speaker_id: int | None = None) -> bool:
    """Generate audio with Piper. Uses multi-speaker model if speaker_id given."""
    try:
        from piper.config import SynthesisConfig
    except ImportError:
        log.warning("Piper not available")
        return False

    voice = None
    if speaker_id is not None:
        voice = _get_piper_multi_voice()
    if voice is None:
        voice = _get_piper_voice()
        speaker_id = None  # primary model is single-speaker
    if voice is None:
        return False

    try:
        syn_config = SynthesisConfig(
            speaker_id=speaker_id,
            length_scale=PIPER_LENGTH_SCALE,
            noise_scale=PIPER_NOISE_SCALE,
            noise_w_scale=PIPER_NOISE_W_SCALE,
        )
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=syn_config)
        path.write_bytes(buf.getvalue())
        return True
    except Exception as e:
        log.error("Piper synthesis failed: %s", e)
        path.unlink(missing_ok=True)
        return False


# ---------------------------------------------------------------------------
# espeak-ng (emergency fallback — always works, robotic)
# ---------------------------------------------------------------------------

def _generate_espeak(text: str, path: Path):
    result = subprocess.run(
        [ESPEAK_CMD, "-v", ESPEAK_VOICE, "-s", str(ESPEAK_SPEED),
         "-p", str(ESPEAK_PITCH), "-g", str(ESPEAK_GAP), "-w", str(path), text],
        capture_output=True, timeout=30,
    )
    if result.returncode != 0:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"espeak-ng failed (rc={result.returncode}): {result.stderr.decode()}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_voice_for_reel(reel_index: int) -> tuple[str, int | None]:
    """Return (edge_voice, piper_speaker_id) for a given reel index.

    Rotates voices so consecutive reels sound different.
    """
    edge_voice = EDGE_VOICES[reel_index % len(EDGE_VOICES)]
    piper_speaker = CURATED_SPEAKERS[reel_index % len(CURATED_SPEAKERS)]
    return edge_voice, piper_speaker


def generate_audio(text: str, reel_index: int = 0) -> Path:
    """Generate TTS audio for the given text.

    Engine priority: edge-tts → Piper → espeak-ng.
    Voice rotates based on reel_index for variety.
    """
    edge_voice, piper_speaker = get_voice_for_reel(reel_index)
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = _content_hash(text, voice_key=edge_voice)
    path = AUDIO_CACHE_DIR / f"{h}.wav"

    if path.exists() and path.stat().st_size > 0:
        return path

    with _tts_lock:
        if path.exists() and path.stat().st_size > 0:
            return path

        # 1. Edge-TTS (primary — near-human quality)
        if _generate_edge_tts(text, path, edge_voice):
            log.info("Edge-TTS generated: voice=%s, %d bytes", edge_voice, path.stat().st_size)
            return path

        # 2. Piper (offline fallback — good quality)
        log.info("Falling back to Piper TTS")
        piper_path = AUDIO_CACHE_DIR / f"{_content_hash(text, f'piper-{piper_speaker}')}.wav"
        if _generate_piper(text, piper_path, speaker_id=piper_speaker):
            # Copy to expected path so cache key works
            import shutil
            shutil.copy2(piper_path, path)
            log.info("Piper generated: speaker=%d, %d bytes", piper_speaker, path.stat().st_size)
            return path

        # 3. espeak-ng (emergency — always works)
        log.info("Falling back to espeak-ng")
        _generate_espeak(text, path)
        return path
