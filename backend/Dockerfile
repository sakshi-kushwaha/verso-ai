FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends espeak-ng ffmpeg fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/embeddings data/audio_cache data/video_cache tts/models

# Download Piper voice models:
# 1. en_US-lessac-high — high quality female narrator (~108MB)
# 2. en_US-libritts_r-medium — 904 speakers for voice variety (~75MB)
RUN python -c "\
import urllib.request, os; \
os.makedirs('tts/models', exist_ok=True); \
hf = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US'; \
models = [('lessac/high', 'en_US-lessac-high'), ('libritts_r/medium', 'en_US-libritts_r-medium')]; \
[urllib.request.urlretrieve(f'{hf}/{m}/{p}{e}', f'tts/models/{p}{e}') for m, p in models for e in ['.onnx', '.onnx.json']]; \
print('Piper voice models downloaded')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
