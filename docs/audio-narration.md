# Audio Narration — TTS Engine

## Overview

Verso generates audio narration for each reel using text-to-speech. The TTS engine converts reel summary text into WAV audio files served via the `/audio/{reel_id}` endpoint.

## Current Engine: Piper TTS (Neural)

We use [Piper](https://github.com/rhasspy/piper) — a fast, local neural TTS engine that produces natural, human-like speech.

- **Model:** `en_US-lessac-medium.onnx` (~60 MB)
- **Sample rate:** 22,050 Hz, 16-bit mono PCM WAV
- **Latency:** ~2s per reel on CPU
- **RAM overhead:** ~40 MB resident after model load

### Why Piper over espeak-ng

The original implementation used espeak-ng (formant synthesizer). It sounded robotic and broken:

| Metric | espeak-ng | Piper TTS |
|--------|-----------|-----------|
| Synthesis type | Formant (mathematical) | Neural (AI-trained) |
| Voice quality | Robotic, unclear | Natural, human-like |
| Avg amplitude | ~1,200 | ~3,500 |
| Silence ratio | 32–48% | 4–13% |
| RAM | 0 MB | ~40 MB |

espeak-ng is kept as an automatic fallback if Piper fails to load.

## Architecture

```
FeedPage (React)
  └─ clicks "Listen"
      └─ GET /audio/{reel_id}
          └─ audio router looks up reel summary in SQLite
              └─ generate_audio(text)
                  ├─ cache hit? → return cached .wav
                  └─ cache miss (under lock):
                      ├─ Piper TTS → synthesize_wav() → .wav
                      └─ fallback: espeak-ng subprocess → .wav
```

### Key files

| File | Purpose |
|------|---------|
| `backend/tts/engine.py` | TTS generation with Piper + espeak-ng fallback |
| `backend/config.py` | TTS config (engine, model path, espeak params) |
| `backend/routers/audio.py` | `/audio/{reel_id}` endpoint |
| `backend/tts/models/` | Piper `.onnx` model files (gitignored, downloaded at Docker build) |

### Caching

Audio files are cached by content hash (SHA-256 of normalized text) in `data/audio_cache/`. Same text always produces the same filename, preventing duplicate generation. A threading lock ensures no concurrent TTS calls.

## Configuration

In `backend/config.py`:

```python
# Choose engine: "piper" (default) or "espeak"
TTS_ENGINE = os.getenv("TTS_ENGINE", "piper")

# Piper
PIPER_MODEL_DIR = Path(__file__).parent / "tts" / "models"
PIPER_MODEL = "en_US-lessac-medium.onnx"

# espeak-ng fallback
ESPEAK_VOICE = "en"       # default male voice
ESPEAK_SPEED = 130        # words per minute
ESPEAK_PITCH = 50         # 0–99
ESPEAK_GAP   = 4          # pause between words
```

To force espeak-ng (e.g. for debugging), set `TTS_ENGINE=espeak` in the environment.

## Docker

The Dockerfile downloads the Piper voice model at build time from HuggingFace. espeak-ng is also installed via apt as a fallback.

## Testing

A Playwright E2E test verifies audio generation end-to-end:

```bash
npx playwright test tests/audio-reel.spec.js
```

The test logs in, navigates to the feed, clicks "Listen", intercepts the audio response, and analyzes the WAV file (format, duration, amplitude, silence ratio).
