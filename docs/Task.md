# Verso - Task Breakdown

**Timeline:** 3 Days (Feb 16–18) | **Demo:** Feb 23
**Target:** EC2 `c6i.xlarge` (4 vCPU, 8 GB RAM, 20 GB gp3 EBS)
**Team:** 3 Full-Stack Engineers

---

## Engineer Assignments (by Feature)

| Engineer | Features | Scope |
|----------|----------|-------|
| **E1** | F3 (Upload & Parsing) + F4 (Reel Generation) + Infra/Docker | Owns the entire backend pipeline from document upload to reel/flashcard output, plus EC2 infra and deployment. |
| **E2** | F7 (Swipeable Feed) + F5 (Flashcards) + F8 (Download & Save) | Owns every user-facing screen — swipeable feed, flashcards, bookmarks, download, and all UI polish. |
| **E3** | F6 (Chat Q&A + RAG) + F1 (Auth) + F2 (Onboarding) + TTS | Owns the RAG-powered chat engine, TTS audio, and then layers on auth and onboarding. |

---

## Day 1 — Core Pipeline + Feed UI + Chat Engine (all dev on EC2)

> All engineers SSH into EC2 from Day 1. Develop directly on the target machine so there are zero "works on my machine" surprises. Ollama runs on EC2 throughout.

### E1 — Infra + Document Upload + Reel Generation Pipeline
- [ ] Provision EC2 `c6i.xlarge`, install Docker, Docker Compose, git
- [ ] Set up Docker Compose: FastAPI container + Ollama container (`:11434`)
- [ ] Pull `qwen2.5:3b` and `nomic-embed-text` on EC2, verify with test prompts
- [ ] Create `data/` directory structure (`verso.db`, `audio_cache/`, `temp/`)
- [ ] Set up FastAPI project structure, Uvicorn, CORS, Pydantic schemas, error middleware
- [ ] Design full SQLite schema (`users`, `user_preferences`, `uploads`, `reels`, `flashcards`, `bookmarks`, `progress`, `chat_history`)
- [ ] Implement document parsing — `pdfplumber` (PDF) + `python-docx` (DOCX), page-by-page
- [ ] Detect chapter boundaries via regex (fallback: 3,000-char chunks)
- [ ] Build document type detection (first 2,000 chars → single LLM call)
- [ ] Build structured prompt templates for reel generation
- [ ] Implement LLM call → JSON parsing with multi-level fallback (valid JSON → regex → raw text fallback)
- [ ] Build background thread pipeline: batch processing (5 pages/batch, 3,000 char cap, section cap = `total_pages / 4`)
- [ ] Implement `/upload` endpoint — multipart, 50 MB limit, save to temp, kick off background thread
- [ ] Implement `/upload/status/{id}` — progress count, batch status
- [ ] Implement `/feed` endpoint — paginated reel list from SQLite
- [ ] Implement `/flashcards` endpoint — list by upload
- [ ] Temp file cleanup after parsing (`os.unlink` in try/finally)

### E2 — Frontend Setup + Feed + Flashcards UI
- [ ] Initialize React + Vite with Tailwind CSS 4.x, React Router 7.x, Zustand 5.x, Axios
- [ ] Set up project structure: pages, components, stores, API layer
- [ ] Build Document Upload page — drag & drop + file picker, file type/size validation (50 MB)
- [ ] Build processing progress indicator — polling `/upload/status/{id}` every 3s
- [ ] Build Swipeable Reel Feed using Swiper.js — full-screen vertical cards
- [ ] Reel card component: title, summary, category badge, keywords, page ref, bookmark icon, audio button
- [ ] Implement infinite scroll with paginated loading (auto-fetch 3 reels from end)
- [ ] Incremental reel loading — new reels appear as batches complete
- [ ] Build main app layout/navigation shell (Feed, Flashcards, Bookmarks, Chat tabs)
- [ ] Build Flashcards page — flip-card UI for self-testing, grouped by document
- [ ] Build Bookmarks/Saved page — list of saved reels and flashcards

### E3 — RAG Engine + Chat + TTS
- [ ] Build chunk embedding pipeline — `nomic-embed-text` via Ollama `/api/embed`
- [ ] Build NumPy cosine similarity search (top-3 chunk retrieval)
- [ ] Build chat prompt template — question + retrieved chunks → grounded answer with source refs
- [ ] Implement `/chat/ask` endpoint — embed question → retrieve → LLM answer
- [ ] Implement chat history storage in SQLite
- [ ] Implement conversation summary generation (on-demand LLM call)
- [ ] Implement exchange limit per document (N exchanges cap)
- [ ] Implement `qa_ready` gating — chat enabled only after embeddings complete
- [ ] Implement TTS module — `espeak-ng` subprocess, `.wav` cached by content hash, `threading.Lock()`
- [ ] Implement `/audio/{reel_id}` — serve cached audio or generate on-demand

**Day 1 Checkpoint:** Upload a PDF on EC2 → reels generated in DB → `/feed` returns them. Feed UI renders reels (can use mock data if API not wired yet). RAG returns relevant chunks for test questions.

---

## Day 2 — Full Integration + Auth + Remaining Features

### E1 — Pipeline Hardening + Edge Cases
- [ ] Wire embedding trigger after all reel batches complete (hand off to E3's RAG pipeline)
- [ ] Handle edge cases: empty PDFs, scanned PDFs (< 50 chars detection), oversized files
- [ ] Add timeout handling for Ollama calls (120–600s per call)
- [ ] Tune LLM prompts for consistent JSON across doc types (textbook, research paper, business)
- [ ] Test graceful degradation: kill Ollama mid-process → verify fallback reels
- [ ] Implement `/bookmarks` CRUD — add/remove bookmark, list bookmarked items
- [ ] Implement `/progress/view` — track viewed reels on swipe
- [ ] Implement `/download` — bundle reels + flashcards + audio as zip
- [ ] `docker stats` check — verify peak RAM < 6.5 GB during processing

### E2 — Chat UI + Bookmarks + Download + Polish
- [ ] Build Chat Q&A page UI — message input, response display with source references, loading states
- [ ] Chat disabled state when `qa_ready = false`, enabled once embeddings done
- [ ] Implement bookmark toggle on reel cards and flashcards (wire to `/bookmarks` API)
- [ ] Build download button/flow (wire to `/download` API)
- [ ] Audio playback on reel cards — play/pause button, GET `/audio/{reel_id}`
- [ ] Build Progress tracking UI — viewing progress per upload
- [ ] Loading states, error states, empty states across all pages
- [ ] Mobile responsiveness — swipe on touch, layout adapts

### E3 — Auth + Onboarding + Integration
- [ ] Implement `/auth/signup` and `/auth/login` — bcrypt hashing, token-based session
- [ ] Implement `/auth/me` for session validation
- [ ] Build Login/Signup UI pages
- [ ] Build Onboarding quiz UI — learning style (visual/auditory/reading) + preferences
- [ ] Implement `/preferences` CRUD — save/retrieve onboarding data
- [ ] Wire auth flow: signup → login → onboarding → redirect to upload
- [ ] Connect learning style to reel generation prompts (visual → bullets, auditory → conversational, reading → detailed)
- [ ] Protected routes — redirect to login if unauthenticated
- [ ] End-to-end test on EC2: signup → onboard → upload → reels → chat → bookmark → download

**Day 2 Checkpoint:** Full flow works end-to-end on EC2 — signup → onboard → upload → reels in feed → flashcards → chat → bookmarks → download. All features functional.

---

## Day 3 — Harden, Polish, Deploy, Demo Prep

### E1 — Production Deploy + Monitoring
- [ ] Docker Compose production config — Ollama `NUM_PARALLEL=1`, restart policies (`unless-stopped`)
- [ ] Implement `/health` endpoint
- [ ] Verify Ollama auto-unload after 5 min idle — idle RAM < 3 GB
- [ ] Verify peak RAM < 6.5 GB during active processing (`docker stats`)
- [ ] Test with 5+ varied documents (textbook, research paper, business doc, fiction, small PDF)
- [ ] Performance: verify < 90s to first reel, < 3 min for 20-page doc
- [ ] Degradation chain test: reel+flashcard+audio → no audio → reel skipped → upload error
- [ ] Security pass: ensure no command injection in file handling, sanitize filenames

### E2 — Final UI Polish
- [ ] Feed smoothness — no jank on swipe (Chrome DevTools profiling)
- [ ] Feed load < 500ms, onboarding < 30s
- [ ] Consistent styling, transitions, feedback indicators across all pages
- [ ] Final responsive pass — mobile + desktop
- [ ] Fix remaining bugs from integration testing

### E3 — Regression Testing + Demo Prep
- [ ] Full regression on EC2: 5 different documents, every feature exercised
- [ ] Verify scanned PDF handling (no crash, user feedback message)
- [ ] Verify all error states display correctly to user
- [ ] Verify chat source references are accurate
- [ ] Prepare demo document (pick a good 15–20 page PDF that produces quality reels)
- [ ] Write demo walkthrough script for Feb 23
- [ ] Final bug sweep and fix

**Day 3 Checkpoint:** App is production-ready on EC2. All 8 features work. Metrics within target. Demo document and script ready.

---

## EC2 Setup Checklist (E1 — first thing Day 1)

```
1. Launch c6i.xlarge (4 vCPU, 8 GB RAM), Ubuntu 22.04, 20 GB gp3 EBS
2. Security group: open ports 3000 (frontend), 8000 (API), 22 (SSH)
3. Install Docker + Docker Compose
4. Install espeak-ng (apt install espeak-ng)
5. Docker Compose up: Ollama container on :11434
6. Pull models: ollama pull qwen2.5:3b && ollama pull nomic-embed-text
7. Verify: curl http://localhost:11434/api/tags → both models listed
8. Set OLLAMA_NUM_PARALLEL=1 in Ollama container env
9. Git clone repo, set up shared access for all 3 engineers
```

---

## Priority Order (if behind schedule)

1. **Must ship:** Upload/Parse → Reel Generation → Feed (F3, F4, F7)
2. **High:** Flashcards → Chat Q&A (F5, F6)
3. **Medium:** Bookmarks → Download (F8)
4. **Lower:** Auth (F1), Onboarding personalization (F2), TTS audio, progress tracking
