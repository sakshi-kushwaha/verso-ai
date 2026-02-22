import os
import secrets
from pathlib import Path

# ── JWT Secret ──────────────────────────────────────────────
_ENV_FILE = Path(os.path.dirname(__file__)) / ".env"


def _get_or_create_jwt_secret() -> str:
    """Return JWT secret from env, .env file, or generate one."""
    val = os.getenv("JWT_SECRET")
    if val:
        return val
    # Try reading from .env file
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            if line.startswith("JWT_SECRET="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    # Generate and persist
    generated = secrets.token_hex(32)
    with open(_ENV_FILE, "a") as f:
        f.write(f"\nJWT_SECRET={generated}\n")
    return generated


JWT_SECRET: str = _get_or_create_jwt_secret()

# Ollama
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL: str = "nomic-embed-text"
EMBED_DIM: int = 768

# Chunking
CHUNK_MAX_CHARS: int = 500
CHUNK_OVERLAP_CHARS: int = 50

# RAG retrieval
TOP_K: int = 3

# Paths
DATA_DIR: Path = Path("data")
EMBEDDINGS_DIR: Path = DATA_DIR / "embeddings"
AUDIO_CACHE_DIR: Path = DATA_DIR / "audio_cache"
VIDEO_CACHE_DIR: Path = DATA_DIR / "video_cache"

# Stock assets
STOCK_VIDEOS_DIR: Path = Path(os.path.dirname(__file__)) / "static" / "stock-videos"
SOUND_EFFECTS_DIR: Path = Path(os.path.dirname(__file__)) / "static" / "sound-effects"

# TTS — "piper" (neural, high quality) or "espeak" (formant, robotic fallback)
TTS_ENGINE: str = os.getenv("TTS_ENGINE", "piper")

# Piper TTS (neural voice)
PIPER_MODEL_DIR: Path = Path(os.path.dirname(__file__)) / "tts" / "models"
PIPER_MODEL: str = "en_GB-jenny_dioco-medium.onnx"  # warm British female — best Piper narrator
PIPER_SPEAKER_ID = None  # int or None
# Multi-speaker model for voice variety across reels
PIPER_MULTI_MODEL: str = "en_US-libritts_r-medium.onnx"

# espeak-ng fallback
ESPEAK_CMD: str = "espeak-ng"
ESPEAK_VOICE: str = "en"
ESPEAK_SPEED: int = 130
ESPEAK_PITCH: int = 50
ESPEAK_GAP: int = 4

# LLM — multi-model routing
LLM_MODEL: str = "qwen2.5:3b"  # legacy default, used by generate_reel_script / chat
CLASSIFICATION_MODEL: str = os.getenv("CLASSIFICATION_MODEL", "qwen2.5:1.5b")
REEL_MODEL: str = os.getenv("REEL_MODEL", "qwen2.5:1.5b")
CHAT_MODEL: str = os.getenv("CHAT_MODEL", "qwen2.5:3b")
LLM_TIMEOUT: float = 300.0

# Chat
MAX_EXCHANGES_PER_DOC: int = 10

# Timeouts
OLLAMA_EMBED_TIMEOUT: float = 30.0
