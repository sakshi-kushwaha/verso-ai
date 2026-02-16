import hashlib
import subprocess
import threading
from pathlib import Path
from config import AUDIO_CACHE_DIR, ESPEAK_CMD, ESPEAK_VOICE, ESPEAK_SPEED

_tts_lock = threading.Lock()


def _content_hash(text: str) -> str:
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_audio_path(text: str) -> Path | None:
    h = _content_hash(text)
    path = AUDIO_CACHE_DIR / f"{h}.wav"
    return path if path.exists() else None


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

        result = subprocess.run(
            [
                ESPEAK_CMD,
                "-v", ESPEAK_VOICE,
                "-s", str(ESPEAK_SPEED),
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

        return path
