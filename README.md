# Verso

**Learn Smarter, Scroll Better**

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + Vite, Tailwind CSS, Zustand, Swiper.js, Axios |
| Backend | Python 3.11+, FastAPI, Uvicorn, pdfplumber, python-docx, NumPy |
| LLM | Qwen 2.5 3B (Q4) via Ollama |
| Embedding | nomic-embed-text via Ollama |
| TTS | espeak-ng |
| Database | SQLite |
| Containerization | Docker Compose |

## Setup

### Run with Docker

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| Ollama | http://localhost:11434 |

### Run without Docker

**Backend:**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

### Pushed final version 01 on 21 April 2026
