import os
from pathlib import Path

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
PIPER_MODEL: str = "en_US-lessac-high.onnx"
PIPER_SPEAKER_ID = None  # int or None
# Multi-speaker model for voice variety across reels
PIPER_MULTI_MODEL: str = "en_US-libritts_r-medium.onnx"

# espeak-ng fallback
ESPEAK_CMD: str = "espeak-ng"
ESPEAK_VOICE: str = "en"
ESPEAK_SPEED: int = 130
ESPEAK_PITCH: int = 50
ESPEAK_GAP: int = 4

# LLM
LLM_MODEL: str = "qwen2.5:3b"
LLM_TIMEOUT: float = 300.0

# Chat
MAX_EXCHANGES_PER_DOC: int = 10

# Timeouts
OLLAMA_EMBED_TIMEOUT: float = 30.0
