# Verso AI — Comprehensive Technical Documentation

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Deep Dive](#2-architecture-deep-dive)
3. [AI Pipeline](#3-ai-pipeline)
4. [Algorithm & Feed Ranking](#4-algorithm--feed-ranking)
5. [Database Schema](#5-database-schema)
6. [Backend API Reference](#6-backend-api-reference)
7. [Document Processing Pipeline](#7-document-processing-pipeline)
8. [RAG (Retrieval-Augmented Generation) Pipeline](#8-rag-retrieval-augmented-generation-pipeline)
9. [TTS (Text-to-Speech) Pipeline](#9-tts-text-to-speech-pipeline)
10. [Frontend Architecture](#10-frontend-architecture)
11. [Memory Management](#11-memory-management)
12. [Concurrency & Error Handling](#12-concurrency--error-handling)
13. [Docker & Deployment](#13-docker--deployment)
14. [Testing & Validation](#14-testing--validation)
15. [Security Considerations](#15-security-considerations)
16. [Known Limitations & Future Improvements](#16-known-limitations--future-improvements)
17. [Appendix](#17-appendix)

---

## 1. System Overview

### What Verso Does

Verso AI is a fully offline, AI-powered learning platform that transforms uploaded documents (PDFs and DOCX files) into short-form educational "reels" — bite-sized video or text summaries with narration, flashcards, and an interactive Q&A chatbot. Users upload study materials and Verso automatically parses, classifies, and generates a personalized learning feed ranked by their interaction behavior. The entire system runs on a single 8 GB RAM, CPU-only EC2 instance with no external API calls, making it completely self-contained and privacy-preserving.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        EC2 Instance (8 GB RAM)                  │
│                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │   React Frontend │    │   FastAPI Backend │                   │
│  │   (Vite + SPA)   │───▶│   (Uvicorn)      │                   │
│  │   Port: 5173     │    │   Port: 8000      │                   │
│  │   (dev only)     │    │                    │                   │
│  └──────────────────┘    │  ┌──────────────┐ │   ┌────────────┐ │
│                          │  │  Pipeline    │ │   │   Ollama    │ │
│  In production,         │  │  (parse →    │ │──▶│   LLM      │ │
│  frontend is served     │  │   classify → │ │   │   Service   │ │
│  as static files by     │  │   generate → │ │   │   Port:     │ │
│  FastAPI                │  │   embed)     │ │   │   11434     │ │
│                          │  └──────────────┘ │   └────────────┘ │
│                          │                    │                   │
│                          │  ┌──────────────┐ │                   │
│                          │  │  SQLite DB   │ │                   │
│                          │  │  (WAL mode)  │ │                   │
│                          │  └──────────────┘ │                   │
│                          └──────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### Tech Stack Summary

| Layer | Technology | Details |
|-------|-----------|---------|
| **Frontend** | React 19, Vite 7, Tailwind CSS 4 | SPA with Zustand 5 state management, Swiper.js 12 carousel |
| **Backend** | Python 3.11, FastAPI, Uvicorn | Async API with WebSocket support for real-time progress |
| **AI / LLM** | Ollama (local), Qwen 2.5 | 1.5B for classification + reel gen, 3B for chat |
| **Embeddings** | nomic-embed-text (768-dim) | Local vector embeddings for RAG pipeline |
| **TTS** | Edge-TTS, Piper (ONNX), espeak-ng | Three-tier fallback: neural cloud → neural local → formant |
| **Video** | FFmpeg, Pillow | 1080p vertical video composition with text overlays |
| **Database** | SQLite 3 (WAL mode) | 13 tables, parameterized queries, auto-migrations |
| **Infrastructure** | EC2 (Ubuntu 24.04), GitHub Actions | CI/CD pipeline, systemd for Ollama |

### Constraints

- **RAM**: 8 GB total, 5.5 GB safe ceiling for peak usage
- **CPU-only**: No GPU — all LLM inference runs on CPU (~4 tok/s)
- **No external APIs**: Fully offline after initial model download (Edge-TTS is the one exception for higher-quality narration, with Piper as offline fallback)
- **Single-writer database**: SQLite with WAL mode for concurrent reads

---

## 2. Architecture Deep Dive

### Container Architecture (Docker Compose)

The development environment uses Docker Compose with three services:

```yaml
services:
  backend:    # FastAPI + Uvicorn
    build: ./backend
    ports: ["8000:8000"]
    volumes:
      - ./backend:/app
      - backend_data:/app/data
    depends_on: [ollama]
    restart: unless-stopped

  frontend:   # Vite dev server
    build: ./frontend
    ports: ["5173:5173"]
    depends_on: [backend]
    restart: unless-stopped

  ollama:     # LLM inference
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes: [ollama_data:/root/.ollama]
    environment:
      OLLAMA_MAX_LOADED_MODELS: 1
    restart: unless-stopped
```

**Production** runs differently — no Docker containers. Backend runs directly via `uvicorn` in a Python venv, Ollama runs as a systemd service, and the frontend is pre-built static files served by FastAPI.

### Service-to-Service Communication

```
Frontend ──HTTP/WS──▶ Backend ──HTTP──▶ Ollama
                          │
                          ▼
                      SQLite DB
                      (file-based)
```

- **Frontend → Backend**: HTTP REST API + WebSocket (upload progress, chat streaming)
- **Backend → Ollama**: HTTP API calls to `http://ollama:11434` (Docker) or `http://localhost:11434` (production)
- **Backend → SQLite**: Direct file I/O via Python's `sqlite3` module

### Port Mapping

| Port | Service | Purpose |
|------|---------|---------|
| 5173 | Vite (dev only) | Frontend dev server with HMR |
| 8000 | FastAPI/Uvicorn | API + static frontend (production) |
| 11434 | Ollama | LLM inference API |

### Request Lifecycle

```
1. User uploads PDF via browser
2. Frontend POST /upload (multipart form data)
3. FastAPI validates file (type, size ≤ 50 MB)
4. File saved to temp directory
5. Background thread spawned for pipeline processing
6. WebSocket connection opened for real-time progress
7. Pipeline: parse → classify → extract topics → generate reels + video → embed for RAG
8. Each reel pushed to frontend via WebSocket as it's generated
9. Frontend renders reel in Swiper carousel
10. User interactions (view, skip, like, bookmark) tracked
11. Feed re-ranked on next fetch based on interaction history
```

---

## 3. AI Pipeline

### Model Selection

| Model | Size | Use Case | Why Chosen |
|-------|------|----------|------------|
| `qwen2.5:1.5b` | ~1 GB RAM | Classification, reel generation | Fast on CPU (~4 tok/s), good instruction following for structured JSON output |
| `qwen2.5:3b` | ~2 GB RAM | Chat Q&A | Better reasoning for open-ended questions while staying within memory budget |
| `nomic-embed-text` | ~300 MB | Document embeddings (768-dim) | Compact, performant, good semantic understanding |

**What was tried and rejected**: Larger models (7B+) exceeded the 8 GB RAM constraint when coexisting with the backend and video processing. The 1.5B model proved sufficient for structured generation (JSON reels) while the 3B model was reserved for the more demanding chat task.

### Quantization

Ollama handles quantization automatically. The Qwen 2.5 models use Q4_K_M quantization by default, which provides ~4-bit precision. This reduces model size by ~4x compared to FP16 with minimal quality degradation for the structured output tasks Verso requires.

### Prompt Engineering

#### Document Classification Prompt

```
Classify this document by BOTH its type and subject area.
Document types: textbook, research_paper, business, fiction, technical, general
Subject categories: science, math, history, literature, business, technology,
                    medicine, law, arts, engineering, general
Rules:
- Respond with ONLY two words separated by a space: doc_type subject_category
- No explanation, no punctuation, no extra text.
Text: {text}
Classification:
```

#### Topic Extraction Prompt

```
Identify the {num_topics} most important distinct topics covered.
For each topic, provide:
- "topic": A clear, specific topic name (3-8 words)
- "keywords": 3-5 keywords that would appear in text about this topic
Rules:
1. Return ONLY valid JSON, no extra text.
2. Topics must be distinct — no overlapping or redundant topics.
3. Order topics by importance (most important first).
4. Each topic should be specific enough to make one focused reel.
Schema: {"topics":[{"topic":"specific topic name","keywords":"word1, word2, word3"}]}
Text: {text}
JSON:
```

#### Reel Generation Prompt (with Video Clips)

```
Generate exactly ONE reel with video clip selections and 1-2 flashcards
about {topic}.

TOPIC: {topic}
DOCUMENT TYPE: {doc_type}
STYLE: {style_instruction}        # visual/auditory/reading/mixed
LENGTH: {depth_instruction}        # brief/balanced/detailed
FOCUS: {use_case_instruction}      # exam/work/learning/research
DIFFICULTY: {difficulty_instruction} # easy/medium/hard

AVAILABLE VIDEO CLIPS (use ONLY these filenames for segments):
{clip_list}

RULES:
1. Return ONLY valid JSON — no extra text.
2. Narration must be 40-60 words, conversational (contractions, pauses).
3. Pick exactly {num_segments} clips, durations sum to {total_duration}s.
4. Each segment overlay max 8 words.
5. "one_liner" under 15 words — the reel's most surprising insight.

Schema: {
  "reels": [{
    "title": "short catchy title",
    "summary": "key idea",
    "narration": "spoken version with contractions and ... pauses",
    "one_liner": "one punchy sentence",
    "category": "topic area",
    "keywords": "comma separated",
    "segments": [{"clip": "filename.mp4", "overlay": "short text", "duration": 5}]
  }],
  "flashcards": [{"question": "question?", "answer": "detailed answer ≥10 words"}]
}
```

**System Prompt (Reel Generation):**
```
You are Verso, a learning content creator who teaches through short reels.
You are NOT a textbook. You explain like a friend.

CRITICAL RULES:
1. Use at least 3 contractions (don't, isn't, you're, it's, here's).
2. Use "..." at least once and "—" at least once.
3. NEVER use: "is defined as", "refers to the process", "plays a crucial role".
4. Narration MUST be 40-60 words.
5. Always output valid JSON with "reels" and "flashcards" arrays.
```

#### Chat Q&A Prompt

The chat system uses RAG — the top 3 most relevant document chunks are retrieved via cosine similarity and injected into the prompt:

```
You are Verso, a helpful study assistant. Answer the student's question using
ONLY the provided context. If the context doesn't contain enough information,
say so honestly.

Context:
{retrieved_chunks}

Chat history:
{recent_history}

Question: {user_question}
```

### JSON Output Schema

**Expected reel output:**
```json
{
  "reels": [{
    "title": "string (≤60 chars)",
    "summary": "string",
    "narration": "string (40-60 words)",
    "one_liner": "string (≤15 words)",
    "category": "string",
    "keywords": "string (comma-separated)",
    "segments": [
      {"clip": "category/filename.mp4", "overlay": "string (≤8 words)", "duration": 5}
    ]
  }],
  "flashcards": [
    {"question": "string ending with ?", "answer": "string (≥10 words)"}
  ]
}
```

### Fallback Parsing Logic

When the LLM returns malformed output, `parse_llm_json` applies a three-level fallback:

1. **Level 1**: Direct `json.loads()` on the raw response
2. **Level 2**: Regex extraction — find `{...}` or `[...]` blocks in the response
3. **Level 3**: Construct a fallback "Summary" reel using the raw text as the summary field

Field defaults when missing:
- `narration` → falls back to `summary`
- `one_liner` → first 120 chars of `summary`
- `category` → `"general"`
- `keywords` → empty string

### Token Budget

| Component | Tokens |
|-----------|--------|
| System prompt | ~200 |
| Reel generation prompt template | ~400 |
| Topic content (3000 chars) | ~750 |
| Few-shot examples | ~300 |
| **Total input** | **~1,650** |
| Context window | 4,096 (reel) / 2,048 (classification) |
| Max output (`num_predict`) | 600 (reel) / 20 (classification) / 300 (summary) |

### LLM Configuration

```python
# Reel generation
temperature=0.3, num_ctx=4096, num_predict=600

# Classification
temperature=0.1, num_ctx=2048, num_predict=20

# Chat
temperature=0.3, num_ctx=2048, num_predict=400
```

---

## 4. Algorithm & Feed Ranking

### Cold Start Strategy

New users with zero interactions receive a default category affinity of **0.5** (neutral) for all categories. The feed ordering for new users is determined by:

1. **Recency** (15% weight) — newer reels ranked higher
2. **Novelty** (25% weight) — all reels are novel (unseen), so this is uniformly 1.0
3. **Popularity** (10% weight) — globally liked/bookmarked content rises
4. **Random jitter** (0–3%) — prevents deterministic ordering

Platform seed reels (from the "Explore" tab) are pre-loaded and ranked similarly, providing immediate content before a user uploads anything.

### Interaction Tracking

Events captured per reel interaction:

| Event | Trigger | Value |
|-------|---------|-------|
| `view` | User stays on reel ≥ 2 seconds | `time_spent_ms` |
| `skip` | User swipes away in < 2 seconds | `time_spent_ms` |
| `like` | User taps heart icon | — |
| `unlike` | User untaps heart icon | — |
| `bookmark` | User saves reel | — |
| `unbookmark` | User unsaves reel | — |

All events are stored in the `reel_interactions` table with user_id, reel_id, action, time_spent_ms, and timestamp.

### Skip vs Watch Definition

```javascript
// Frontend: useReelTracker.js
const SKIP_THRESHOLD_MS = 2000  // 2 seconds

if (elapsed < SKIP_THRESHOLD_MS) {
  trackInteraction(reelId, 'skip', elapsed)
} else {
  trackInteraction(reelId, 'view', elapsed)
}
```

- **Skip**: User leaves reel in under 2 seconds
- **Watch/View**: User stays on reel for 2+ seconds
- Timer starts on `onSlideEnter` (Swiper slide change)
- Timer flushes on next slide change, tab visibility change, or component unmount

### Preference Inference Logic

Category affinities are computed from raw interactions:

```python
# algorithm.py — build_user_profile()
WEIGHTS = {
    'like':     +3.0,
    'bookmark': +2.0,
    'view':     +1.0,   # if time_spent_ms > 5000
    'view':     +0.5,   # if time_spent_ms 2000-5000
    'skip':     -1.5,
}

# For each interaction:
#   category_raw_scores[reel.category] += WEIGHTS[action]

# Normalize to [0, 1]:
min_score = min(raw_scores.values())
max_score = max(raw_scores.values())
normalized[cat] = (raw - min_score) / (max_score - min_score + 1e-10)
```

### Feed Ranking Formula

```python
def score_reel(reel, profile, popularity, now):
    # 1. Category Affinity (40%)
    affinity = profile["category_scores"].get(reel.category, 0.5)

    # 2. Novelty (25%)
    novelty = 0.0 if reel.id in profile["viewed_reel_ids"] else 1.0

    # 3. Recency (15%) — exponential decay
    age_hours = (now - reel.created_at).total_seconds() / 3600
    recency = 2 ** (-age_hours / 168)  # half-life = 7 days

    # 4. Popularity (10%)
    pop = popularity.get(reel.id, 0.0)  # normalized likes + bookmarks

    # 5. Seen Penalty (10%)
    seen = 1.0 if (reel.id in viewed and reel.id not in liked|bookmarked) else 0.0

    # 6. Jitter (0-3%) — prevents deterministic ties
    jitter = random.uniform(0, 0.03)

    score = (0.40 * affinity
           + 0.25 * novelty
           + 0.15 * recency
           + 0.10 * pop
           - 0.10 * seen
           + jitter)

    return score
```

### Platform & PDF Reel Interleaving

- **Explore tab**: Shows only seed/gold-standard reels (doc_type = 'seed'), ranked by the algorithm
- **For You tab**: Shows only the user's own uploaded document reels, ranked by the algorithm
- **My Documents tab**: Single-document view, reels in chronological order
- The two tabs provide natural separation rather than interleaving within a single feed

### Exploration vs Exploitation

- **Exploration**: The 3% random jitter ensures that even low-affinity categories occasionally surface. The novelty weight (25%) strongly favors unseen content over repeat views.
- **Exploitation**: Category affinity (40%) is the dominant signal, so liked categories dominate.
- **Anti-bubble mechanism**: The seen penalty only applies to viewed content that wasn't liked or bookmarked, ensuring that positive interactions keep content visible even after viewing.

---

## 5. Database Schema

### Full Schema

```sql
-- Users & Authentication
CREATE TABLE users (
    id              INTEGER PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    created_at      TEXT DEFAULT (datetime('now')),
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until    TEXT
);

CREATE TABLE user_preferences (
    user_id              INTEGER PRIMARY KEY REFERENCES users(id),
    display_name         TEXT DEFAULT '',
    learning_style       TEXT CHECK(learning_style IN ('visual','auditory','reading','mixed')) DEFAULT 'mixed',
    content_depth        TEXT CHECK(content_depth IN ('brief','balanced','detailed')) DEFAULT 'balanced',
    use_case             TEXT CHECK(use_case IN ('exam','work','learning','research')) DEFAULT 'learning',
    flashcard_difficulty  TEXT CHECK(flashcard_difficulty IN ('easy','medium','hard')) DEFAULT 'medium',
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now'))
);

CREATE TABLE refresh_tokens (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    device_info TEXT,
    ip_address  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL,
    revoked     INTEGER DEFAULT 0
);
CREATE INDEX idx_rt_user ON refresh_tokens(user_id);
CREATE INDEX idx_rt_hash ON refresh_tokens(token_hash);

CREATE TABLE security_questions (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    question    TEXT NOT NULL,
    answer_hash TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_sq_user ON security_questions(user_id);

-- Content
CREATE TABLE uploads (
    id               INTEGER PRIMARY KEY,
    user_id          INTEGER REFERENCES users(id),
    filename         TEXT NOT NULL,
    status           TEXT DEFAULT 'processing',  -- processing|done|error|partial
    doc_type         TEXT,
    total_pages      INTEGER DEFAULT 0,
    progress         INTEGER DEFAULT 0,
    stage            TEXT DEFAULT 'uploading',
    error_message    TEXT,
    qa_ready         INTEGER DEFAULT 0,
    doc_summary      TEXT,
    chat_summary     TEXT,
    subject_category TEXT DEFAULT 'general',
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE reels (
    id          INTEGER PRIMARY KEY,
    upload_id   INTEGER REFERENCES uploads(id),
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL,
    narration   TEXT,
    one_liner   TEXT,
    category    TEXT,
    keywords    TEXT,
    page_ref    INTEGER,
    audio_path  TEXT,
    video_path  TEXT,
    bg_image    TEXT,
    source_text TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE flashcards (
    id          INTEGER PRIMARY KEY,
    upload_id   INTEGER REFERENCES uploads(id),
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- User Activity
CREATE TABLE bookmarks (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER REFERENCES users(id),
    reel_id       INTEGER REFERENCES reels(id),
    flashcard_id  INTEGER REFERENCES flashcards(id),
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE progress (
    user_id         INTEGER REFERENCES users(id),
    upload_id       INTEGER REFERENCES uploads(id),
    viewed_reel_ids TEXT DEFAULT '[]',
    last_viewed_at  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, upload_id)
);

CREATE TABLE reel_interactions (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    reel_id       INTEGER NOT NULL REFERENCES reels(id),
    action        TEXT NOT NULL CHECK(action IN ('view','like','unlike','skip','bookmark','unbookmark')),
    time_spent_ms INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_ri_user ON reel_interactions(user_id);
CREATE INDEX idx_ri_user_action ON reel_interactions(user_id, action);

CREATE TABLE reel_likes (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    reel_id    INTEGER NOT NULL REFERENCES reels(id),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, reel_id)
);

-- Chat
CREATE TABLE chat_history (
    id           INTEGER PRIMARY KEY,
    upload_id    INTEGER REFERENCES uploads(id),
    user_message TEXT NOT NULL,
    ai_response  TEXT NOT NULL,
    sources      TEXT DEFAULT '[]',
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE chat_summaries (
    id             INTEGER PRIMARY KEY,
    upload_id      INTEGER REFERENCES uploads(id),
    summary        TEXT NOT NULL,
    session_number INTEGER DEFAULT 1,
    created_at     TEXT DEFAULT (datetime('now'))
);
```

### ER Diagram

```
users ──────┬──────── user_preferences (1:1)
  │         ├──────── refresh_tokens (1:N)
  │         ├──────── security_questions (1:N)
  │         ├──────── bookmarks (1:N)
  │         ├──────── progress (1:N)
  │         ├──────── reel_interactions (1:N)
  │         └──────── reel_likes (1:N)
  │
  └──── uploads ────┬──── reels ────┬──── bookmarks
            │       │               ├──── reel_interactions
            │       │               └──── reel_likes
            │       ├──── flashcards ──── bookmarks
            │       ├──── chat_history
            │       └──── chat_summaries
            │
            └──── progress
```

### Key Queries

**Feed ranking query:**
```sql
SELECT r.*, u.doc_type, u.subject_category
FROM reels r
JOIN uploads u ON r.upload_id = u.id
WHERE u.user_id = ? AND u.status IN ('done', 'partial')
ORDER BY r.created_at DESC
```
(Scoring is applied in Python after retrieval)

**Preference calculation:**
```sql
SELECT ri.action, ri.time_spent_ms, r.category
FROM reel_interactions ri
JOIN reels r ON ri.reel_id = r.id
WHERE ri.user_id = ?
```

**Progress tracking:**
```sql
SELECT u.id, u.filename, u.doc_type,
    (SELECT COUNT(*) FROM reels WHERE upload_id = u.id) AS total_reels,
    (SELECT COUNT(*) FROM flashcards WHERE upload_id = u.id) AS total_flashcards
FROM uploads u WHERE u.user_id = ? AND u.status = 'done'
ORDER BY u.created_at DESC
```

### Migration Strategy

Migrations are auto-applied on startup in `database.py`:
- `ALTER TABLE ADD COLUMN IF NOT EXISTS` for new columns
- Table creation uses `CREATE TABLE IF NOT EXISTS`
- Default user (id=1) seeded for backward compatibility
- Orphan uploads backfilled to user_id=1

No separate migration tool — the `init_db()` function handles all schema evolution idempotently.

---

## 6. Backend API Reference

### Auth Endpoints

| Method | Path | Request Body | Response | Status |
|--------|------|-------------|----------|--------|
| POST | `/auth/signup` | `{name, password, remember_me?}` | `{user: {id, name}, token, refresh_token}` | 200, 400, 409 |
| POST | `/auth/login` | `{name, password, remember_me?}` | `{user: {id, name}, token, refresh_token}` | 200, 401, 429 |
| POST | `/auth/refresh` | `{refresh_token}` | `{token, refresh_token}` | 200, 401 |
| POST | `/auth/logout` | `{refresh_token}` | `{ok: true}` | 200 |
| GET | `/auth/me` | — | `{id, name, display_name, preferences}` | 200, 401 |
| PUT | `/auth/profile` | `{display_name?, current_password?, new_password?}` | `{message}` | 200, 400, 401 |
| DELETE | `/auth/account` | `{password}` | `{message}` | 200, 401 |
| GET | `/auth/sessions` | — | `[{id, device_info, ip_address, created_at}]` | 200 |
| DELETE | `/auth/sessions/{id}` | — | `{message}` | 200 |
| POST | `/auth/sessions/revoke-all` | — | `{message}` | 200 |
| POST | `/auth/security-questions` | `{questions: [{question, answer}]}` | `{message}` | 200, 400 |
| POST | `/auth/forgot-password/verify` | `{name, answers}` | `{reset_token}` | 200, 401 |
| POST | `/auth/forgot-password/reset` | `{reset_token, new_password}` | `{message}` | 200, 401 |

### Upload Endpoints

| Method | Path | Request Body | Response | Status |
|--------|------|-------------|----------|--------|
| POST | `/upload` | Multipart: `file` (PDF/DOCX, ≤50MB) | `{id, filename, status}` | 200, 400 |
| GET | `/upload/status/{id}` | — | `{status, progress, stage, reels_count, error_message?}` | 200, 404 |
| GET | `/uploads` | — | `[{id, filename, status, doc_type, reel_count, flashcard_count, total_pages}]` | 200 |
| WS | `/ws/upload/{id}` | — | `{type: "progress"|"reel_ready"|"flashcard_ready", ...}` | — |
| DELETE | `/upload/{upload_id}` | — | `{message: "Document deleted"}` | 200, 404 |

### Feed Endpoints

| Method | Path | Query Params | Response | Status |
|--------|------|-------------|----------|--------|
| GET | `/feed` | `page, limit, upload_id?, tab?` | `{reels: [...], total, page, has_more}` | 200 |

**Tab values**: `all` (For You), `explore` (seed reels), `my-docs`, or a specific `upload_id`.

### Interaction Tracking

| Method | Path | Request Body | Response | Status |
|--------|------|-------------|----------|--------|
| POST | `/interactions/track` | `{reel_id, action, time_spent_ms?}` | `{status: "ok"}` | 200 |
| POST | `/interactions/batch` | `[{reel_id, action, time_spent_ms?}, ...]` | `{status: "ok", count: N}` | 200 |
| GET | `/interactions/likes` | — | `{liked_reel_ids: [...]}` | 200 |

### Bookmarks

| Method | Path | Request Body | Response | Status |
|--------|------|-------------|----------|--------|
| GET | `/bookmarks` | — | `[{id, reel_id, flashcard_id, reel_title, ...}]` | 200 |
| POST | `/bookmarks` | `{reel_id?} or {flashcard_id?}` | `{id, message}` | 200 |
| DELETE | `/bookmarks/{id}` | — | `{message}` | 200, 404 |

### Flashcards

| Method | Path | Query Params | Response | Status |
|--------|------|-------------|----------|--------|
| GET | `/flashcards` | `upload_id?` | `[{id, question, answer, upload_id}]` | 200 |

### Chat

| Method | Path | Request/Params | Response | Status |
|--------|------|-------------|----------|--------|
| POST | `/chat/ask` | `{upload_id, question}` | `{answer, sources}` | 200, 409, 429 |
| GET | `/chat/history/{upload_id}` | — | `[{user_message, ai_response, sources, created_at}]` | 200 |
| GET | `/chat/status/{upload_id}` | — | `{qa_ready, exchange_count, limit, remaining, has_summary}` | 200 |
| GET | `/chat/summary/{upload_id}` | — | `{summaries: [{summary, session, created_at}]}` | 200 |
| POST | `/chat/new-session/{upload_id}` | — | `{message, session_number}` | 200 |
| WS | `/ws/chat/{upload_id}` | `{question}` | Stream: `stream_start → token* → stream_end` | — |

### Audio & Video

| Method | Path | Response | Status |
|--------|------|----------|--------|
| GET | `/audio/{reel_id}` | WAV file | 200, 404, 503 |
| GET | `/audio/summary/{upload_id}` | WAV file | 200, 404, 503 |
| GET | `/video/{reel_id}` | MP4 file | 200, 404 |
| GET | `/video/{reel_id}/download` | MP4 with title overlay | 200, 404 |

### Progress

| Method | Path | Request Body | Response | Status |
|--------|------|-------------|----------|--------|
| POST | `/progress/view` | `{upload_id, reel_id}` | `{message}` | 200 |
| GET | `/progress/{upload_id}` | — | `{viewed_reel_ids, viewed_count, total_reels, percent}` | 200 |
| GET | `/progress` | — | `{overall_percent, total_reels_viewed, uploads: [...]}` | 200 |

### Health

| Method | Path | Response |
|--------|------|----------|
| GET | `/health` | `{"status": "ok"}` |

---

## 7. Document Processing Pipeline

### Upload Flow

```
User selects file
    │
    ▼
POST /upload (multipart)
    │
    ├── Validate file extension (.pdf, .docx only)
    ├── Validate file size (≤ 50 MB)
    ├── Save to TEMP_DIR
    ├── Create upload record in DB (status: 'processing')
    ├── Spawn background daemon thread → process_upload()
    └── Return {upload_id, status: 'processing'}
```

### PDF Parsing (pdfplumber)

```python
def parse_pdf(file_path):
    pages = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append({"page": i + 1, "text": text})

    total_text = "".join(p["text"] for p in pages)
    if len(total_text.strip()) < 50:
        raise ScannedPDFError("PDF appears to be scanned")

    return pages
```

### DOCX Parsing (python-docx)

```python
def parse_docx(file_path):
    doc = Document(file_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    # Split into pseudo-pages of CHUNK_SIZE (3000 chars)
    chunks = chunk_text(full_text, CHUNK_SIZE)
    return [{"page": i + 1, "text": chunk} for i, chunk in enumerate(chunks)]
```

### Chunking Strategy

- **Sentence-level splitting**: Text is split at `. ` boundaries
- **Max chunk**: 3,000 characters
- **Fallback**: Word-level split if a single sentence exceeds max
- **Chapter detection**: Regex for `^(chapter|section|part)\s+\d+`

### Section Cap Logic

```python
num_topics = max(3, min(total_pages // 2.5, 100))
# ~1 reel per 2.5 pages, minimum 3, maximum 100
```

### Background Thread Processing

```python
def process_upload(upload_id, file_path, filename, user_id):
    # Runs in daemon thread
    try:
        # 1. Parse → 2. Classify → 3. Extract topics
        # 4. For each topic: generate reel + video → save to DB → notify via WS
        # 5. Deferred: generate summary + embed chunks for RAG
    except Exception:
        mark_upload_error(upload_id, str(error))
    finally:
        cleanup_temp_file(file_path)
```

### Progressive Delivery

Each reel is pushed to the frontend immediately after generation via WebSocket:

```python
# After saving reel to DB:
asyncio.run_coroutine_threadsafe(
    manager.broadcast_reel_ready(upload_id, reel_dict),
    _event_loop
)
```

The frontend receives `reel_ready` events and appends reels to the Swiper carousel in real time, so users can start browsing before the full document is processed.

### Polling Mechanism

Frontend polls `/upload/status/{id}` every 3 seconds as a fallback when WebSocket is unavailable:

```javascript
const poll = setInterval(async () => {
    const { data } = await api.get(`/upload/status/${uploadId}`)
    updateBgUpload(data)
    if (data.status === 'done' || data.status === 'error') clearInterval(poll)
}, 3000)
```

---

## 8. RAG (Retrieval-Augmented Generation) Pipeline

### Embedding Model

- **Model**: `nomic-embed-text` via Ollama
- **Dimensions**: 768
- **API**: `POST http://ollama:11434/api/embed`
- **Timeout**: 60 seconds per batch

### Document Chunk Embedding

```python
def embed_chunks(upload_id, full_text):
    # 1. Chunk text: 500 chars max, 50 char overlap
    chunks = chunk_for_embedding(full_text)

    # 2. Embed each chunk
    vectors = []
    for chunk in chunks:
        vec = embed_text(chunk)  # 768-dim float vector
        vectors.append(vec)

    # 3. Save to disk
    np.save(f"{EMBEDDINGS_DIR}/{upload_id}_vectors.npy", np.array(vectors, dtype=np.float32))
    json.dump(chunks, open(f"{EMBEDDINGS_DIR}/{upload_id}_chunks.json", "w"))
```

### Chunk Size and Overlap

```python
CHUNK_MAX_CHARS = 500     # Max characters per embedding chunk
CHUNK_OVERLAP_CHARS = 50  # Overlap between consecutive chunks
```

Sentence-level splitting with overlap ensures that concepts spanning sentence boundaries are captured in at least one chunk.

### Cosine Similarity Search

```python
def retrieve(upload_id, question, top_k=3):
    # 1. Embed the question
    q_vec = np.array(embed_text(question), dtype=np.float32)

    # 2. Load stored embeddings
    chunks, vectors = load_embeddings(upload_id)

    # 3. L2 normalize
    q_norm = q_vec / (np.linalg.norm(q_vec) + 1e-10)
    v_norms = vectors / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-10)

    # 4. Cosine similarity (dot product of normalized vectors)
    similarities = v_norms @ q_norm

    # 5. Top-K retrieval
    top_indices = np.argsort(similarities)[::-1][:top_k]
    return [{"chunk": chunks[i], "score": float(similarities[i]), "index": i}
            for i in top_indices]
```

### Chat Q&A Flow

```
User question
    │
    ▼
embed_text(question) → 768-dim vector
    │
    ▼
cosine_similarity(question_vec, all_chunk_vecs) → scores
    │
    ▼
top_3_chunks = sorted by score, take top 3
    │
    ▼
prompt = system_prompt + context(top_3_chunks) + chat_history + question
    │
    ▼
LLM (qwen2.5:3b) → answer
    │
    ▼
Save to chat_history, return {answer, sources}
```

### Limitations

- **Max exchanges per document**: 10 (configurable via `MAX_EXCHANGES_PER_DOC`)
- **Context window**: 2,048 tokens for chat model
- **Chat history cap**: 2,000 characters of recent history included in prompt
- **Embeddings are on-disk**: Loaded into memory on each query (no persistent vector DB)

---

## 9. TTS (Text-to-Speech) Pipeline

### Three-Tier Engine Priority

| Priority | Engine | Type | Quality | Offline |
|----------|--------|------|---------|---------|
| 1 | Edge-TTS | Microsoft Neural | High (natural) | No (requires internet) |
| 2 | Piper | ONNX Neural | Medium (good) | Yes |
| 3 | espeak-ng | Formant synthesis | Low (robotic) | Yes |

### Edge-TTS Configuration (Primary)

```python
EDGE_VOICES = [
    "en-IN-NeerjaExpressiveNeural",  # expressive Indian female
    "en-IN-PrabhatNeural",           # clear Indian male
    "en-IN-NeerjaNeural",            # warm Indian female
    "en-GB-SoniaNeural",             # warm British female
]
# Voice rotates by reel_index % len(EDGE_VOICES) for variety
# Rate: "-5%" (slightly slower for clarity)
```

- Generates MP3, converts to WAV (22050 Hz, mono, PCM S16LE)
- Extracts sentence-level timestamps for caption synchronization
- Saves timestamps as JSON sidecar file

### Piper Configuration (Offline Fallback)

```python
PIPER_MODEL = "en_GB-jenny_dioco-medium.onnx"      # ~60MB, warm British narrator
PIPER_MULTI_MODEL = "en_US-libritts_r-medium.onnx"  # ~75MB, 904 speakers

PIPER_LENGTH_SCALE = 1.15    # Slightly slower speech
PIPER_NOISE_SCALE = 0.7     # Phoneme-level variance
PIPER_NOISE_W_SCALE = 0.9   # Duration variance

CURATED_SPEAKERS = [3, 14, 28, 45, 60, 92, 118, 175]
# Selected for clarity and natural sound from 904 available speakers
```

### espeak-ng Configuration (Emergency Fallback)

```python
ESPEAK_CMD = "espeak-ng"
ESPEAK_VOICE = "en"
ESPEAK_SPEED = 130    # words per minute
ESPEAK_PITCH = 50     # 0-99 range
ESPEAK_GAP = 4        # ms between words
```

Note: The engine priority is fixed (Edge → Piper → espeak). The `TTS_ENGINE`
environment value is not used to override this order; fallbacks are automatic
based on availability.

### Content Hash Caching

```python
def generate_audio(text, reel_index=0):
    voice_key = get_voice_for_reel(reel_index)
    cache_key = hashlib.sha256((text.lower().strip() + str(voice_key)).encode()).hexdigest()
    cache_path = AUDIO_CACHE_DIR / f"{cache_key}.wav"

    if cache_path.exists():
        return cache_path  # Cache hit

    with _tts_lock:  # Thread-safe
        if cache_path.exists():  # Double-check after lock
            return cache_path

        # Generate audio (Edge-TTS → Piper → espeak-ng)
        ...
        return cache_path
```

- **Hash function**: SHA-256 of `lowercase(text) + voice_key`
- **File naming**: `{hash}.wav` in `AUDIO_CACHE_DIR`
- **Thread locking**: `threading.Lock()` prevents concurrent TTS calls
- **Double-check pattern**: Check cache before and after acquiring lock

### Audio Output

- **Format**: WAV (PCM S16LE, 22050 Hz, mono)
- **Typical size**: ~100-300 KB per 15-second reel narration
- **Served via**: `GET /audio/{reel_id}` → `FileResponse`

---

## 10. Frontend Architecture

### Folder Structure

```
frontend/src/
├── api/
│   ├── index.js           # Axios instance + all API endpoints
│   └── ws.js              # WebSocket URL helpers
├── assets/                # Static assets
├── components/
│   ├── Button.jsx         # Primary button with variants
│   ├── Icons.jsx          # SVG icon library
│   ├── Input.jsx          # Form input
│   ├── ProtectedRoute.jsx # Auth guard + auto-load bookmarks/likes
│   ├── StateScreens.jsx   # Spinner, EmptyState, ErrorState
│   ├── UploadTracker.jsx  # Background upload progress banner
│   ├── SplashScreen.jsx   # Loading screen
│   ├── PasswordStrength.jsx
│   ├── MobileBackButton.jsx
│   └── Tag.jsx            # Category badge
├── hooks/
│   └── useReelTracker.js  # Interaction tracking (skip vs view)
├── layouts/
│   ├── MainLayout.jsx     # Sidebar + topbar
│   └── AuthLayout.jsx     # Login/signup wrapper
├── pages/
│   ├── FeedPage.jsx       # Main feed (Swiper carousel)
│   ├── BookmarksPage.jsx  # Saved items
│   ├── FlashcardsPage.jsx # 3D flip flashcards
│   ├── UploadPage.jsx     # Document upload
│   ├── ChatPage.jsx       # Q&A with WebSocket streaming
│   ├── MyBooksPage.jsx    # Collections + processing UI
│   ├── ProfilePage.jsx    # Settings & logout
│   ├── LoginPage.jsx
│   ├── SignupPage.jsx
│   ├── OnboardingPage.jsx
│   ├── LandingPage.jsx
│   └── HelpPage.jsx
├── services/
│   ├── tts.js             # Server + browser TTS fallback
│   └── audioCache.js      # IndexedDB audio caching (LRU, max 50)
├── store/
│   └── useStore.js        # Zustand global store
├── utils/
│   └── reelMapper.js      # API → UI reel format mapper
├── App.jsx                # Route definitions
├── main.jsx               # React entry point
└── index.css              # Tailwind + custom animations
```

### Component Hierarchy

```
<BrowserRouter>
  <App>
    <Routes>
      ├── <ProtectedRoute>              # Auth guard
      │   └── <MainLayout>              # Sidebar + topbar
      │       ├── <FeedPage />          # "/"
      │       ├── <BookmarksPage />     # "/bookmarks"
      │       ├── <UploadPage />        # "/upload"
      │       ├── <FlashcardsPage />    # "/flashcards"
      │       ├── <ChatPage />          # "/chat"
      │       ├── <MyBooksPage />       # "/books"
      │       ├── <ProfilePage />       # "/profile"
      │       └── <HelpPage />          # "/help"
      ├── <LandingPage />              # "/welcome"
      ├── <OnboardingPage />           # "/onboarding"
      └── <AuthLayout>
          ├── <LoginPage />            # "/login"
          └── <SignupPage />           # "/signup"
```

### State Management (Zustand)

The single Zustand store (`useStore.js`) manages:

| State Group | Keys | Persistence |
|-------------|------|-------------|
| **Auth** | `user`, `token`, `refreshToken` | localStorage |
| **Onboarding** | `displayName`, `userRole`, `onboarded` | localStorage |
| **Bookmarks** | `bookmarks` (Map), `bookmarkItems` (array) | API-backed |
| **Likes** | `likes` (Map) | API-backed |
| **Feed** | `reels`, `feedPage`, `hasMore` | In-memory |
| **Playback** | `muted` | In-memory |
| **Upload** | `currentUpload`, `bgUpload` | In-memory |

### Swiper.js Integration

```javascript
<Swiper
  direction="vertical"
  modules={[Mousewheel, Keyboard]}
  mousewheel={{ forceToAxis: true, thresholdDelta: 30, thresholdTime: 300 }}
  keyboard
  slidesPerView={1}
  speed={400}
  onReachEnd={loadMoreReels}    // Infinite scroll (next 50 reels)
  onSlideChange={(swiper) => {
    setActiveIndex(swiper.activeIndex)
    onSlideEnter(reels[swiper.activeIndex].id)  // Track interaction
  }}
>
  {reels.map((reel) => (
    <SwiperSlide key={reel.id}>
      {reel.videoUrl ? <VideoReelCard /> : <GradientPostCard />}
    </SwiperSlide>
  ))}
</Swiper>
```

**Card types**:
- `VideoReelCard`: HTML5 video with progress bar, autoplay when active
- `ReelCard`: Text card with gradient accent and TTS listen button
- `GradientPostCard`: Full-screen gradient background with staggered text animations

### Axios Interceptors

```javascript
// Request: Attach JWT token
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('verso_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
})

// Response: Auto-refresh expired tokens
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        if (error.response?.status === 401 && !originalRequest._retry) {
            // Refresh token, queue concurrent requests, retry
        }
    }
)
```

Features a subscriber queue pattern: when multiple requests fail with 401 simultaneously, only one refresh is performed and all queued requests are retried with the new token.

### Responsive Design

- **Framework**: Tailwind CSS 4 with custom theme
- **Breakpoints**: `sm:640px` (mobile nav), `md:768px`, `lg:1024px`
- **Mobile**: Bottom navigation bar replaces sidebar; safe-area insets for iPhone notch
- **Dark theme**: Default — deep dark background (`#0A0F1A`), glass morphism topbar
- **Fonts**: Outfit (headings), DM Sans (body), IBM Plex Mono (code)

Dev proxy note (EC2): Vite's proxy points to `backend:8000`. On a single
host, add a hosts entry so `backend` resolves locally:

```
grep -q '^127.0.0.1 backend$' /etc/hosts || echo '127.0.0.1 backend' >> /etc/hosts
```

---

## 11. Memory Management

### RAM Budget

| Component | Idle | Peak Processing |
|-----------|------|----------------|
| Ollama (qwen2.5:1.5b loaded) | ~1.2 GB | ~1.5 GB |
| Ollama (qwen2.5:3b loaded) | ~2.0 GB | ~2.5 GB |
| Ollama (nomic-embed-text) | ~300 MB | ~400 MB |
| FastAPI backend | ~150 MB | ~400 MB |
| FFmpeg video encoding | — | ~400 MB |
| SQLite + WAL | ~10 MB | ~50 MB |
| **Total (reel gen)** | **~1.7 GB** | **~2.7 GB** |
| **Total (chat + embed)** | **~2.5 GB** | **~3.3 GB** |
| **Worst case** | — | **~5.3 GB** |

Safe ceiling: **5.5 GB** of 8 GB total.

### Preventing Model Coexistence

```yaml
# docker-compose (dev)
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_NUM_PARALLEL=1

# EC2 production (ec2-setup.sh)
# Default override: NUM_PARALLEL=2
```

Ollama automatically unloads the current model before loading a different one. In Docker compose we keep a single loaded model and one parallel request; the EC2 setup uses two parallel requests by default. The pipeline is designed so that reel generation (1.5B) completes before chat (3B) or embedding (nomic) models are needed, thanks to the deferred embedding strategy.

### Input Size Caps

| Cap | Value | Rationale |
|-----|-------|-----------|
| Max file upload | 50 MB | Prevents memory spikes during parsing |
| Doc summary input | 6,000 chars | Fits comfortably in 4K context window |
| Topic extraction sample | 6,000 chars (retries 10K) | Balanced coverage vs context window |
| Topic content per reel | 3,000 chars | ~750 tokens, leaves room for prompt + output |
| Chat history in prompt | 2,000 chars | Prevents context window overflow |
| Reel narration | 40-60 words | Matches 15-second video target |
| Source text stored | 5,000 chars | Reference only, not used for LLM calls |

### Temp File Cleanup

```python
# In pipeline.py, after processing:
finally:
    if os.path.exists(temp_path):
        os.remove(temp_path)
```

Uploaded files are cleaned up in the `finally` block of the pipeline processing function, ensuring cleanup even on errors.

---

## 12. Concurrency & Error Handling

### Single Background Thread Model

Each document upload spawns a single daemon thread:

```python
thread = threading.Thread(
    target=process_upload,
    args=(upload_id, temp_path, filename, user_id),
    daemon=True
)
thread.start()
```

Within this thread, video composition is parallelized via a ThreadPoolExecutor (max 2 workers), so LLM calls and video encoding overlap.

### Thread Locking Strategy

| Lock | Type | Purpose |
|------|------|---------|
| `_tts_lock` | `threading.Lock()` | Prevents concurrent TTS synthesis (espeak-ng/Piper are not thread-safe) |
| `ConnectionManager._lock` | `asyncio.Lock()` | Protects WebSocket subscription dictionary |
| SQLite WAL mode | Built-in | Allows concurrent reads, serializes writes |

### Ollama Serialization

```ini
OLLAMA_NUM_PARALLEL=1
```

Ollama processes one request at a time per its `NUM_PARALLEL` setting. In Docker we use 1; in EC2 setup we default to 2. The pipeline makes sequential LLM calls per topic. Chat requests are serialized at the application level.

### Uvicorn Concurrency (operations)

- Single worker to avoid SQLite multi-process contention.
- Higher concurrency helps many GETs (especially `/video` Range requests) in parallel.

Examples:

```
# Read-heavy (video playback):
nohup uvicorn main:app --host 0.0.0.0 --port 8000 \
  --workers 1 --limit-concurrency 200 --timeout-keep-alive 15 \
  >/root/verso-ai/server.log 2>&1 &

# During multiple uploads (avoid writer lock contention):
nohup uvicorn main:app --host 0.0.0.0 --port 8000 \
  --workers 1 --limit-concurrency 20 --timeout-keep-alive 15 \
  >/root/verso-ai/server.log 2>&1 &
```

### SQLite Under FastAPI Async

FastAPI runs async, but SQLite calls are synchronous. The pattern used:

```python
def get_db():
    conn = sqlite3.connect(str(DATA_DIR / "verso.db"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

Each request gets its own connection. WAL mode enables concurrent readers. Writes are serialized by SQLite's internal locking (acceptable for single-instance deployment).

### Timeout Configurations

| Timeout | Value | Purpose |
|---------|-------|---------|
| `LLM_TIMEOUT` | 300s | Per-LLM-call timeout |
| `REEL_LLM_TIMEOUT` | 300s | Reel generation call |
| `CLASSIFICATION_TIMEOUT` | 90s | Document classification |
| `OLLAMA_EMBED_TIMEOUT` | 60s | Embedding batch |
| `PIPELINE_TIMEOUT` | 3600s (60 min) | Total upload processing |
| `STALE_UPLOAD_MINUTES` | 30 min | Auto-fail stuck uploads |
| `FFMPEG_ENCODE_TIMEOUT` | 180s | Video encoding per clip |

### Graceful Degradation Chain

```
Full pipeline:
  Reel + Video + Audio ← ideal
    │ video fails
    ▼
  Reel + Audio (no video) ← video composition silently skipped
    │ TTS fails (all 3 engines)
    ▼
  Reel only (text card) ← frontend renders as gradient text card
    │ reel generation fails
    ▼
  Skip topic, try next ← partial results still saved
    │ all topics fail
    ▼
  Upload marked "error" ← user sees error message

TTS degradation:
  Edge-TTS (neural, online)
    │ fails (no internet / rate limit)
    ▼
  Piper (neural, offline ONNX)
    │ fails (model missing / OOM)
    ▼
  espeak-ng (formant, always works)
    │ fails (binary missing)
    ▼
  503 "TTS failed" ← reel still available without audio
```

### What Happens When Ollama Crashes

1. **Connection error** → `OllamaUnavailableError` raised
2. LLM calls retry with exponential backoff (up to 3 attempts, delays: 1s, 2s, 4s)
3. If all retries fail → upload marked "error" with message "AI service unavailable"
4. Docker restart policy (`unless-stopped`) automatically restarts Ollama
5. Next upload attempt will succeed once Ollama is healthy

### Bad JSON from LLM

1. Direct `json.loads()` attempt
2. Regex extraction of `{...}` blocks
3. Fallback to single "Summary" reel with raw text
4. If even fallback fails → skip this topic, continue with next

---

## 13. Docker & Deployment

### docker-compose.yml (Annotated)

```yaml
services:
  backend:
    build: ./backend                    # Python 3.11-slim + espeak-ng + ffmpeg
    ports: ["8000:8000"]
    volumes:
      - ./backend:/app                  # Live code reload in development
      - backend_data:/app/data          # Persistent: DB, embeddings, audio/video cache
      - ./scripts:/scripts
    environment:
      OLLAMA_HOST: http://ollama:11434  # Docker service discovery
    depends_on: [ollama]                # Start after Ollama
    restart: unless-stopped

  frontend:
    build: ./frontend                   # Node 20-slim + Vite
    ports: ["5173:5173"]
    volumes:
      - ./frontend:/app
      - /app/node_modules               # Prevents host node_modules conflicts
    depends_on: [backend]
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes:
      - ollama_data:/root/.ollama       # Persistent model storage
    environment:
      OLLAMA_MAX_LOADED_MODELS: 1       # Memory constraint: only 1 model at a time
    restart: unless-stopped

volumes:
  backend_data:    # SQLite DB + embeddings + audio/video cache
  ollama_data:     # Ollama models (~3-4 GB)
```

### Backend Dockerfile

```dockerfile
FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends espeak-ng ffmpeg fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN mkdir -p data/embeddings data/audio_cache data/video_cache tts/models

# Download Piper TTS voice models (~135 MB total)
RUN python -c "
import urllib.request, os
os.makedirs('tts/models', exist_ok=True)
hf = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/en'
models = [
    ('en_GB/jenny_dioco/medium', 'en_GB-jenny_dioco-medium'),
    ('en_US/libritts_r/medium', 'en_US-libritts_r-medium')
]
[urllib.request.urlretrieve(f'{hf}/{m}/{p}{e}', f'tts/models/{p}{e}')
 for m, p in models for e in ['.onnx', '.onnx.json']]
print('Piper voice models downloaded')"

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### Frontend Dockerfile

```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
```

### EC2 Setup (Production)

```bash
# ec2-setup.sh — idempotent setup for Ubuntu 24.04, 8 GB RAM
bash ec2-setup.sh          # Full setup (first time)
bash ec2-setup.sh --deploy # Deploy mode (CI/CD, skip Ollama install)
```

Steps:
1. Install system packages: `python3-venv, espeak-ng, ffmpeg, fonts-dejavu-core`
2. Install Ollama via curl, configure systemd (defaults to `NUM_PARALLEL=2`)
3. Pull models: `qwen2.5:1.5b`, `qwen2.5:3b`, `nomic-embed-text`
4. Create Python venv, install `requirements.txt`
5. Download Piper voice models from HuggingFace
6. Create data directories

### Publish Frontend (preserve stock media)

Sync the Vite build into `backend/static` without overwriting stock assets:

```
cd /root/verso-ai/frontend
npm ci || npm install
npm run build
apt-get update -qq && apt-get install -y -qq rsync
rsync -av --delete \
  --exclude 'stock-videos/' --exclude 'sound-effects/' --exclude 'bg-images/' \
  /root/verso-ai/frontend/dist/ /root/verso-ai/backend/static/
```

Then restart the backend as shown in Concurrency (operations).

### GitHub Actions CI/CD

```yaml
# .github/workflows/deploy.yml
on: push to main

jobs:
  deploy:
    1. Checkout code
    2. npm ci && npm run build (frontend)
    3. rsync built frontend to EC2:/root/verso-ai/backend/static/ (exclude stock-videos/, sound-effects/, bg-images/)
    4. SSH: git pull, bash ec2-setup.sh --deploy
    5. SSH: kill uvicorn, restart with nohup
    6. Health check: curl http://localhost:8000/health
```

### Health Check

```
GET /health → {"status": "ok"}
```

Used by CI/CD to verify successful deployment.

### Notes on Video Concurrency

The `/video/{reel_id}` endpoint supports HTTP Range and browsers may open many
parallel requests. Keep a single Uvicorn worker (for SQLite) but use a higher
`--limit-concurrency` (100–200) during playback-heavy workloads.

---

## 14. Testing & Validation

### Reel Quality Validation

- **Manual spot-checks**: Reels reviewed for accuracy, readability, and engagement
- **Narration quality**: Verified conversational tone with contractions and natural pauses
- **Flashcard quality**: Verified questions end with `?`, answers ≥ 10 words

### JSON Parse Success Rate

The three-level fallback parsing (direct → regex → fallback reel) ensures near-100% success rate. The fallback "Summary" reel is used as a last resort when the LLM produces completely malformed output.

### Reel Generation Success Rate

- Per-topic retry: up to 3 attempts per topic
- Partial completion: If some topics fail, successful reels are still saved (status: "partial")
- Only marked "error" if zero reels generated

### Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Empty PDF | 400 "Document has no extractable text" |
| Scanned PDF | Detected (< 50 chars total), 400 "PDF appears to be scanned" |
| 500-page document | Capped at 100 topics/reels; pipeline timeout at 60 minutes |
| Corrupted file | pdfplumber/python-docx raise exception → 400 error |
| Non-English text | Processed but quality depends on Qwen 2.5's multilingual ability |
| Image-heavy documents | Text extraction misses images; reels based on available text only |

### Feed Ranking Validation

- Category affinity weights confirmed to change based on like/skip/view behavior
- Novelty bonus (25%) ensures new content surfaces above repeat views
- Seen penalty demotes already-viewed content that wasn't favorited

---

## 15. Security Considerations

### Password Hashing

```python
import bcrypt

# Hashing
password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# Verification
bcrypt.checkpw(password.encode(), stored_hash.encode())
```

- **Algorithm**: bcrypt with random salt
- **Password requirements**: 8+ characters, at least one uppercase, one lowercase, one digit
- **Account lockout**: 5 failed attempts → 15-minute lock

### Input Validation

- **Pydantic models**: All request bodies validated via Pydantic BaseModel
- **File upload**: Extension whitelist (.pdf, .docx only), 50 MB size limit
- **Query params**: Type-validated by FastAPI's path/query parameter declarations

### SQL Injection Prevention

All queries use parameterized statements:

```python
conn.execute("SELECT * FROM users WHERE name = ?", (username,))
# Never: f"SELECT * FROM users WHERE name = '{username}'"
```

### Token Security

- **Access tokens**: JWT, 30-minute expiry, signed with `JWT_SECRET`
- **Refresh tokens**: 48-byte URL-safe random (`secrets.token_urlsafe`), stored as SHA-256 hash
- **Token rotation**: Old refresh token revoked when new one is issued
- **Reset tokens**: 10-minute expiry, purpose-scoped JWT, validated via security questions

### Rate Limiting

```python
login_limiter = RateLimiter(max_attempts=5, window_seconds=900)
# Sliding window: 5 attempts per 15 minutes per IP:username
```

### File Upload Security

- Filename is not used in file paths (only `upload_id`)
- Files stored in isolated `TEMP_DIR`, cleaned up after processing
- No directory traversal possible

### Offline Verification

No external network calls during normal operation (Edge-TTS is the only exception, with Piper as offline fallback). All LLM inference, embedding, and document processing happens locally.

---

## 16. Known Limitations & Future Improvements

### What Doesn't Work Well

| Limitation | Impact |
|-----------|--------|
| **Scanned PDFs** | No OCR — scanned documents are rejected outright |
| **Non-English content** | Qwen 2.5 has multilingual ability but prompts are English-only; quality degrades |
| **Image-heavy documents** | Images are not extracted or analyzed; only text-based content becomes reels |
| **Single-instance** | No horizontal scaling; one EC2 instance handles all users |
| **TTS quality** | Edge-TTS requires internet; Piper is decent but not human-quality; espeak-ng is robotic |
| **Long documents (500+ pages)** | Pipeline may take 30-60 minutes; 100-reel cap means later content may be lost |
| **Concurrent uploads** | Multiple simultaneous uploads compete for LLM and CPU resources |
| **No image generation** | Background images are pre-assigned from a static library, not AI-generated |
| **Video composition speed** | FFmpeg on CPU is slow; each video takes 10-30 seconds to encode |

### With 16 GB RAM + GPU (Prioritized)

1. **Upgrade to 7B model** for significantly better reel quality and chat responses
2. **Add OCR** (Tesseract or PaddleOCR) for scanned PDF support
3. **GPU-accelerated inference** — 10-50x speedup for LLM calls
4. **Multi-modal understanding** — extract and describe images from documents
5. **Persistent vector database** (ChromaDB or FAISS) instead of on-disk numpy files
6. **Real-time collaboration** — multiple users viewing/editing the same document
7. **Smarter chunking** — semantic chunking based on topic boundaries rather than character counts
8. **A/B testing framework** for reel generation prompts
9. **Better TTS** — local Coqui XTTS or Bark for high-quality offline narration
10. **Video generation** — AI-generated visuals instead of stock clips

---

## 17. Appendix

### Full Database Schema SQL

See [Section 5: Database Schema](#5-database-schema) for the complete `CREATE TABLE` statements.

### Sample LLM Prompts

#### Classification Prompt (Copy-Paste Ready)

```
Classify this document by BOTH its type and subject area.
Document types: textbook, research_paper, business, fiction, technical, general
Subject categories: science, math, history, literature, business, technology, medicine, law, arts, engineering, general
Rules:
- Respond with ONLY two words separated by a space: doc_type subject_category
- No explanation, no punctuation, no extra text.
Text: Photosynthesis is the process by which green plants convert sunlight into chemical energy. The light-dependent reactions occur in the thylakoid membranes...
Classification:
```

**Expected response**: `textbook science`

#### Reel Generation Prompt (Copy-Paste Ready)

```
Generate exactly ONE reel with video clip selections and 1-2 flashcards about Photosynthesis Light Reactions.
TOPIC: Photosynthesis Light Reactions
DOCUMENT TYPE: textbook
Extract key concepts, definitions, learning objectives
STYLE: Write as if talking directly to the reader. Use at least one of: 'you', 'imagine', 'think of', 'let's', 'consider', 'notice'
LENGTH: 2-4 sentences, 40-80 words. Cover main idea with supporting context.
FOCUS: Focus on understanding and why things work. Flashcard questions test comprehension.
DIFFICULTY: Require understanding — explain, compare, describe.

AVAILABLE VIDEO CLIPS:
- science/molecules.mp4: Molecular structures floating
- science/plant_cell.mp4: Plant cell diagram animation
- science/sunlight.mp4: Sunlight rays on leaves
- general/abstract_blue.mp4: Abstract blue particles

RULES: [... as defined in Section 3 ...]

Relevant text about "Photosynthesis Light Reactions":
The light-dependent reactions of photosynthesis occur in the thylakoid membranes of chloroplasts. When chlorophyll absorbs light energy, it excites electrons which are passed through an electron transport chain. This process splits water molecules, releasing oxygen as a byproduct and generating ATP and NADPH...

JSON:
```

### Sample LLM Response (Raw JSON)

```json
{
  "reels": [{
    "title": "How Plants Capture Sunlight",
    "summary": "Light-dependent reactions in thylakoid membranes convert sunlight into ATP and NADPH through an electron transport chain, splitting water and releasing oxygen.",
    "narration": "Here's the thing... plants don't just sit in the sun. They're running a tiny power plant inside their cells. Chlorophyll grabs light energy and kicks electrons down a chain — kind of like a relay race. Along the way, water gets split, oxygen's released, and you get ATP and NADPH. That's the fuel for making sugar.",
    "one_liner": "Plants run a molecular power plant inside every leaf",
    "category": "Biology",
    "keywords": "photosynthesis, light reactions, thylakoid, chlorophyll, ATP",
    "segments": [
      {"clip": "science/sunlight.mp4", "overlay": "Sunlight hits the leaf", "duration": 4},
      {"clip": "science/plant_cell.mp4", "overlay": "Inside the chloroplast", "duration": 4},
      {"clip": "science/molecules.mp4", "overlay": "Electrons cascade down", "duration": 4},
      {"clip": "general/abstract_blue.mp4", "overlay": "ATP and NADPH created", "duration": 3}
    ]
  }],
  "flashcards": [
    {
      "question": "Where do light-dependent reactions of photosynthesis take place?",
      "answer": "Light-dependent reactions occur in the thylakoid membranes of chloroplasts, where chlorophyll absorbs light energy to drive the electron transport chain."
    },
    {
      "question": "What are the main products of the light-dependent reactions?",
      "answer": "The light-dependent reactions produce ATP and NADPH as energy carriers, along with oxygen as a byproduct from the splitting of water molecules."
    }
  ]
}
```

### API Request/Response Examples

#### Upload a Document

```bash
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@biology_textbook.pdf"
```

```json
{"id": 42, "filename": "biology_textbook.pdf", "status": "processing"}
```

#### Check Upload Status

```bash
curl http://localhost:8000/upload/status/42 \
  -H "Authorization: Bearer <token>"
```

```json
{
  "status": "processing",
  "progress": 45,
  "stage": "generating",
  "reels_count": 8,
  "error_message": null
}
```

#### Get Feed

```bash
curl "http://localhost:8000/feed?page=1&limit=5&tab=all" \
  -H "Authorization: Bearer <token>"
```

```json
{
  "reels": [
    {
      "id": 101,
      "title": "How Plants Capture Sunlight",
      "summary": "Light-dependent reactions...",
      "narration": "Here's the thing...",
      "one_liner": "Plants run a molecular power plant",
      "category": "Biology",
      "keywords": "photosynthesis, light reactions",
      "page_ref": 12,
      "video_path": "/app/data/video_cache/reel_101.mp4",
      "bg_image": "bg-images/science_1.jpg"
    }
  ],
  "total": 42,
  "page": 1,
  "has_more": true
}
```

#### Track Interaction

```bash
curl -X POST http://localhost:8000/interactions/track \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"reel_id": 101, "action": "view", "time_spent_ms": 8500}'
```

```json
{"status": "ok"}
```

#### Ask a Question (Chat)

```bash
curl -X POST http://localhost:8000/chat/ask \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"upload_id": 42, "question": "What is the role of chlorophyll?"}'
```

```json
{
  "answer": "Chlorophyll is the green pigment in plant cells that absorbs light energy, primarily in the blue and red wavelengths. It plays a central role in photosynthesis by capturing photons and using that energy to excite electrons, which then drive the electron transport chain in the thylakoid membranes.",
  "sources": ["chunk_12", "chunk_15", "chunk_18"]
}
```

### Performance Benchmark Table

| Pipeline Stage | Typical Duration | Notes |
|----------------|-----------------|-------|
| PDF parsing (50 pages) | 2-5 seconds | pdfplumber, CPU-bound |
| Document classification | 5-15 seconds | qwen2.5:1.5b, ~20 tokens output |
| Topic extraction | 15-30 seconds | qwen2.5:1.5b, ~400 tokens output |
| Reel generation (per topic) | 30-60 seconds | qwen2.5:1.5b, ~600 tokens output |
| Video composition (per reel) | 10-30 seconds | FFmpeg on CPU, overlaps with LLM |
| TTS generation (per reel) | 3-8 seconds | Edge-TTS or Piper |
| Chunk embedding (100 chunks) | 30-60 seconds | nomic-embed-text, sequential |
| Chat response | 10-30 seconds | qwen2.5:3b, RAG retrieval + generation |
| **Full pipeline (20-page PDF)** | **5-10 minutes** | **~8 reels + flashcards + embeddings** |
| **Full pipeline (100-page PDF)** | **20-40 minutes** | **~40 reels, approaches pipeline timeout** |

### Glossary

| Term | Definition |
|------|-----------|
| **Quantization** | Reducing model weight precision (e.g., FP16 → 4-bit) to shrink model size and memory usage with minimal quality loss |
| **RAG** | Retrieval-Augmented Generation — injecting relevant document chunks into an LLM prompt to ground responses in source material |
| **Cosine Similarity** | A measure of similarity between two vectors (0 = unrelated, 1 = identical direction), used to find relevant document chunks for a query |
| **KV Cache** | Key-Value cache in transformer models that stores previously computed attention states to speed up sequential token generation |
| **Cold Start** | The initial state when a new user has no interaction history, requiring default assumptions for feed ranking |
| **WAL Mode** | Write-Ahead Logging in SQLite — enables concurrent read access while writes are serialized, improving performance under load |
| **Embedding** | A dense vector representation of text that captures semantic meaning, enabling similarity search |
| **Token** | The basic unit of text processing for LLMs (roughly ~4 characters or ~0.75 words in English) |
| **Context Window** | The maximum number of tokens an LLM can process in a single call (input + output combined) |
| **Few-Shot** | Providing example inputs and outputs in the prompt to guide the LLM's response format and style |
| **ONNX** | Open Neural Network Exchange — a portable model format used by Piper TTS for cross-platform inference |
| **Formant Synthesis** | A rule-based approach to speech synthesis (used by espeak-ng) that generates sound from acoustic parameters rather than neural networks |
| **SPA** | Single-Page Application — the frontend loads once and handles routing client-side without full page reloads |
| **HMR** | Hot Module Replacement — Vite's development feature that updates code in the browser without a full refresh |

---

*Generated for Verso AI — February 2026*
