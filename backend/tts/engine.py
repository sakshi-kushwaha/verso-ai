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

# Curated speaker IDs from libritts_r that sound clear and natural
# These were selected for clarity, warmth, and suitability for educational narration
CURATED_SPEAKERS = [
    3,    # clear male
    14,   # warm female
    28,   # calm male
    45,   # friendly female
    60,   # expressive male
    92,   # clear female
    118,  # warm male
    175,  # steady female
]

# Slower speech: length_scale > 1.0 = slower, 1.15 ≈ 15% slower for clarity
PIPER_LENGTH_SCALE = 1.18
# Noise scales control expressiveness (higher = more expressive/varied intonation)
PIPER_NOISE_SCALE = 0.7
PIPER_NOISE_W_SCALE = 0.9


def _content_hash(text: str, speaker_id: int | None = None) -> str:
    key = text.strip().lower()
    if speaker_id is not None:
        key += f"|speaker={speaker_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def get_audio_path(text: str) -> Path | None:
    h = _content_hash(text)
    path = AUDIO_CACHE_DIR / f"{h}.wav"
    return path if path.exists() else None


def _load_piper_model(model_name: str):
    """Load a Piper voice model by filename."""
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
    """Lazy-load the primary (single-speaker) Piper voice model."""
    global _piper_voice
    if _piper_voice is not None:
        return _piper_voice
    _piper_voice = _load_piper_model(PIPER_MODEL)
    return _piper_voice


def _get_piper_multi_voice():
    """Lazy-load the multi-speaker Piper voice model."""
    global _piper_multi_voice
    if _piper_multi_voice is not None:
        return _piper_multi_voice
    _piper_multi_voice = _load_piper_model(PIPER_MULTI_MODEL)
    return _piper_multi_voice


def _synthesize_piper(voice, text: str, path: Path, speaker_id: int | None = None) -> bool:
    """Synthesize audio with a Piper voice, using custom speech parameters."""
    try:
        from piper.config import SynthesisConfig

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


def _generate_piper(text: str, path: Path, speaker_id: int | None = None) -> bool:
    """Generate audio with Piper. Uses multi-speaker model if speaker_id given."""
    if speaker_id is not None:
        voice = _get_piper_multi_voice()
        if voice is not None:
            return _synthesize_piper(voice, text, path, speaker_id=speaker_id)
        log.info("Multi-speaker model unavailable, falling back to primary voice")

    voice = _get_piper_voice()
    if voice is None:
        return False
    return _synthesize_piper(voice, text, path)


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


def generate_audio(text: str, speaker_id: int | None = None) -> Path:
    """Generate TTS audio for the given text.

    Args:
        text: The narration text to synthesize.
        speaker_id: Optional speaker ID from CURATED_SPEAKERS for voice variety.
                    If None, uses the primary single-speaker model.
    """
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = _content_hash(text, speaker_id)
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
            if not _generate_piper(text, path, speaker_id=speaker_id):
                log.info("Piper failed, falling back to espeak-ng")
                _generate_espeak(text, path)
        else:
            _generate_espeak(text, path)

        return path
