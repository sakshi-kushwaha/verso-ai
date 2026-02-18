FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends espeak-ng ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/embeddings data/audio_cache data/video_cache tts/models

# Download Piper voice model (en_US-lessac-medium — natural sounding, ~60MB)
RUN python -c "\
import urllib.request, os; \
base = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium'; \
os.makedirs('tts/models', exist_ok=True); \
urllib.request.urlretrieve(f'{base}/en_US-lessac-medium.onnx', 'tts/models/en_US-lessac-medium.onnx'); \
urllib.request.urlretrieve(f'{base}/en_US-lessac-medium.onnx.json', 'tts/models/en_US-lessac-medium.onnx.json'); \
print('Piper voice model downloaded')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
