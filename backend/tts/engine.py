from __future__ import annotations

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
    ESPEAK_CMD,
    ESPEAK_VOICE,
    ESPEAK_SPEED,
    ESPEAK_PITCH,
    ESPEAK_GAP,
)

log = logging.getLogger(__name__)

_tts_lock = threading.Lock()
_piper_voice = None


def _content_hash(text: str) -> str:
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_audio_path(text: str) -> Path | None:
    h = _content_hash(text)
    path = AUDIO_CACHE_DIR / f"{h}.wav"
    return path if path.exists() else None


def _get_piper_voice():
    """Lazy-load Piper voice model (one-time ~2s init)."""
    global _piper_voice
    if _piper_voice is not None:
        return _piper_voice

    try:
        from piper import PiperVoice

        model_path = PIPER_MODEL_DIR / PIPER_MODEL
        config_path = PIPER_MODEL_DIR / f"{PIPER_MODEL}.json"

        if not model_path.exists():
            raise FileNotFoundError(f"Piper model not found: {model_path}")

        _piper_voice = PiperVoice.load(str(model_path), config_path=str(config_path))
        log.info("Piper TTS loaded: %s", PIPER_MODEL)
        return _piper_voice
    except Exception as e:
        log.warning("Piper TTS unavailable (%s), falling back to espeak-ng", e)
        return None


def _generate_piper(text: str, path: Path) -> bool:
    """Generate audio with Piper neural TTS. Returns True on success."""
    voice = _get_piper_voice()
    if voice is None:
        return False

    try:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)

        path.write_bytes(buf.getvalue())
        return True
    except Exception as e:
        log.error("Piper generation failed: %s", e)
        path.unlink(missing_ok=True)
        return False


def _generate_espeak(text: str, path: Path):
    """Generate audio with espeak-ng formant TTS."""
    result = subprocess.run(
        [
            ESPEAK_CMD,
            "-v", ESPEAK_VOICE,
            "-s", str(ESPEAK_SPEED),
            "-p", str(ESPEAK_PITCH),
            "-g", str(ESPEAK_GAP),
            "-w", str(path),
            text,
        ],
        capture_output=True,
        timeout=30,
    )

    if result.returncode != 0:
        path.unlink(missing_ok=True)
        raise RuntimeError(
            f"espeak-ng failed (rc={result.returncode}): {result.stderr.decode()}"
        )


def generate_audio(text: str) -> Path:
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = _content_hash(text)
    path = AUDIO_CACHE_DIR / f"{h}.wav"

    # Fast path: already cached
    if path.exists():
        return path

    # Slow path: generate under lock
    with _tts_lock:
        # Double-check after acquiring lock
        if path.exists():
            return path

        if TTS_ENGINE == "piper":
            if not _generate_piper(text, path):
                log.info("Piper failed, falling back to espeak-ng")
                _generate_espeak(text, path)
        else:
            _generate_espeak(text, path)

        return path
