# Verso - Task Breakdown

**Timeline:** 3 Days (Feb 16–18) | **Demo:** Feb 23
**Target:** EC2 `c6i.xlarge` (4 vCPU, 8 GB RAM, 20 GB gp3 EBS)
**Team:** 3 Full-Stack Engineers

---

## Engineer Assignments (by Feature)

| Engineer | Owns | Scope |
|----------|------|-------|
| **Sakshi** | F3 (Upload & Parsing), F4 (Reel Generation), F9 (Visual Reels), Infra | AI pipeline, image/video extraction, EC2 infra |
| **Esha** | F2 (Onboarding), F6 (Chat Q&A), F5 (Flashcards), All Frontend | Onboarding backend + all UI across every feature |
| **Sanika** | RAG engine, F1 (Auth), F7 (Feed), F8 (Bookmarks/Download), TTS | RAG, auth, feed API, bookmarks/download API, TTS |

---

## Day 1 — Core Pipeline + UI Shell + RAG Engine

> All engineers SSH into EC2 from Day 1. Develop directly on the target machine. Ollama runs on EC2 throughout.

### Sakshi — Infra + Document Upload + Reel Generation Pipeline
- [x] Provision EC2, install Python, espeak-ng, git, curl
- [x] Install Ollama, configure `NUM_PARALLEL=1` and `HOST=0.0.0.0:11434`
- [x] Pull `qwen2.5:3b` and `nomic-embed-text`, verify with test prompts
- [x] Create `data/` directory structure (`verso.db`, `audio_cache/`, `temp/`)
- [x] Set up FastAPI project structure, Uvicorn on port 8000
- [x] Set up CORS, error middleware
- [x] Design full SQLite schema (all tables)
- [x] Implement document parsing — `pdfplumber` (PDF) + `python-docx` (DOCX)
- [x] Detect chapter boundaries via regex (fallback: 3,000-char chunks)
- [x] Build document type detection (first 2,000 chars → single LLM call)
- [x] Build structured prompt templates for reel generation
- [x] Implement LLM call → JSON parsing with multi-level fallback (valid JSON → regex → raw text)
- [x] Build background thread pipeline: batch processing (5 pages/batch, 3,000 char cap, section cap = `total_pages / 4`)
- [x] Implement `/upload` endpoint — multipart, 50 MB limit, save to temp, kick off background thread
- [x] Implement `/upload/status/{id}` — progress count, batch status
- [x] Temp file cleanup after parsing (`os.unlink` in try/finally)

### Esha — Frontend Setup + Flashcards UI
- [x] Initialize React + Vite with Tailwind CSS 4.x, React Router 7.x, Zustand 5.x, Axios
- [x] Set up frontend project structure: pages, components, stores, API layer
- [x] Build main app layout/navigation shell (Feed, Flashcards, Bookmarks, Chat tabs)
- [x] Build Flashcards page — flip-card UI for self-testing, grouped by document
- [x] Build Chat Q&A page UI — message input, response display with source references, loading states
- [x] Build Progress tracking UI — viewing progress per upload
- [x] Implement bookmark toggle on reel cards and flashcards
- [x] Mobile responsiveness — swipe on touch, layout adapts

### Sanika — RAG Engine + Feed UI + TTS
- [x] Build chunk embedding pipeline — `nomic-embed-text` via Ollama `/api/embed`
- [x] Build NumPy cosine similarity search (top-3 chunk retrieval)
- [x] Expose retrieval as internal function for chat endpoint to call
- [x] Build Document Upload page — drag & drop + file picker, file type/size validation (50 MB)
- [x] Build processing progress indicator — polling `/upload/status/{id}` every 3s
- [x] Build Swipeable Reel Feed using Swiper.js — full-screen vertical cards
- [x] Reel card component: title, summary, category badge, keywords, page ref, bookmark icon, audio button
- [x] Implement infinite scroll with paginated loading (auto-fetch 3 reels from end)
- [x] Incremental reel loading — new reels appear as batches complete
- [x] Build Bookmarks/Saved page — list of saved reels and flashcards
- [x] Implement TTS module — `espeak-ng` subprocess, `.wav` cached by content hash, `threading.Lock()`
- [x] Implement `/audio/{reel_id}` — serve cached audio or generate on-demand

**Day 1 Checkpoint:** Upload a PDF on EC2 → reels generated in DB → `/feed` returns them. Feed UI renders reels. RAG returns relevant chunks for test questions. All UI pages built.

**Day 1 Status: COMPLETE** — Full end-to-end backend flow tested: `/upload` → `/upload/status` → `/feed` → `/flashcards` all working. Reels generated from PDF via LLM pipeline.

---

## Day 2 — Onboarding → Chat → Auth → Visual Reels

> **Build order matters:** Onboarding first (preferences stored), then Chat (reads preferences), then Auth (wraps everything). Visual reels pipeline starts in parallel.

### Sakshi — Pipeline Hardening + Visual Reels Pipeline (F9)
- [ ] Wire embedding trigger after all reel batches complete (hand off to RAG pipeline)
- [ ] Handle edge cases: empty PDFs, scanned PDFs (< 50 chars detection), oversized files
- [ ] Add timeout handling for Ollama calls (120–600s per call)
- [ ] Tune LLM prompts for consistent JSON across doc types (textbook, research paper, business)
- [ ] Test graceful degradation: kill Ollama mid-process → verify fallback reels
- [ ] **F9-A:** Extract images from uploaded PDFs using `pdfplumber` image extraction, save per-upload
- [ ] **F9-B:** Curate pre-bundled category illustrations (science, business, literature, tech, general) as fallback when PDF has no extractable images
- [ ] **F9-C:** Curate pre-bundled short looping video clips (~5-10s each) per category for visual learners
- [ ] RAM check — verify peak RAM < 6.5 GB during processing (`free -h`)

### Esha — Onboarding Backend → Chat Backend → Frontend Wiring
- [ ] **F2:** Implement onboarding backend — `/onboarding/preferences` CRUD (save + retrieve user preferences)
- [ ] **F2:** Onboarding stores: learning_style, content_depth, use_case, flashcard_difficulty
- [ ] **F6:** Implement `/chat/ask` — embed question → RAG retrieval → preference-aware LLM answer
- [ ] **F6:** Implement `/chat/history/{upload_id}`, `/chat/status/{upload_id}`, `/chat/summary/{upload_id}`
- [ ] **F6:** Exchange limit per document, `qa_ready` gating (409 if still processing)
- [ ] Chat disabled state in UI when `qa_ready = false`
- [ ] Audio playback on reel cards — play/pause button, GET `/audio/{reel_id}`
- [ ] Build download button/flow in UI (wire to `/download` API)
- [ ] Loading states, error states, empty states across all pages

### Sanika — Auth + Feed/Bookmarks/Download APIs
- [ ] Implement `/auth/signup` and `/auth/login` — bcrypt hashing, token-based session
- [ ] Implement `/auth/me` for session validation
- [ ] Build Login/Signup UI pages
- [ ] Build Onboarding quiz UI — learning style + content depth + use case screens
- [ ] Wire auth flow: signup → login → onboarding → redirect to upload
- [ ] Protected routes — redirect to login if unauthenticated
- [ ] Implement `/feed` endpoint — paginated reel list from SQLite
- [ ] Implement `/flashcards` endpoint — list by upload
- [ ] Implement `/bookmarks` CRUD — add/remove bookmark, list bookmarked items
- [ ] Implement `/progress/view` — track viewed reels on swipe
- [ ] Implement `/download` — bundle reels + flashcards + audio as zip

**Day 2 Checkpoint:** Full flow works end-to-end — signup → onboard → upload → reels in feed → flashcards → chat → bookmarks → download. Preferences personalize chat answers.

---

## Day 3 — Visual Reels Integration + Polish + Demo Prep

### Sakshi — Visual Reels Wiring + Production Hardening
- [x] Ollama production config — `NUM_PARALLEL=1`, systemd restart policies
- [x] Implement `/health` endpoint
- [ ] **F9:** Wire image/video selection into reel generation: attach `media_url` + `media_type` to each reel
- [ ] **F9:** Fallback chain: PDF image → category illustration → no media (text-only)
- [ ] **F9:** Video clips only served when user `learning_style = 'visual'` (read from preferences)
- [ ] Verify Ollama auto-unload after 5 min idle — idle RAM < 3 GB
- [ ] Verify peak RAM < 6.5 GB during active processing
- [ ] Test with 5+ varied documents (textbook, research paper, business doc, fiction, small PDF)
- [ ] Performance: verify < 90s to first reel, < 3 min for 20-page doc
- [ ] Security pass: no command injection in file handling, sanitize filenames

### Esha — Visual Reels UI + Final Polish
- [ ] **F9:** Update reel card to display background image or looping video behind text
- [ ] **F9:** Fallback rendering: video → image → gradient background (graceful degradation)
- [ ] **F9:** Visual learner experience — auto-play muted video loops on reel cards
- [ ] Feed smoothness — no jank on swipe (Chrome DevTools profiling)
- [ ] Feed load < 500ms, onboarding < 30s
- [ ] Consistent styling, transitions, feedback indicators across all pages
- [ ] Final responsive pass — mobile + desktop
- [ ] Fix remaining bugs from integration testing

### Sanika — Regression Testing + Demo Prep
- [ ] Full regression on EC2: 5 different documents, every feature exercised
- [ ] Verify scanned PDF handling (no crash, user feedback message)
- [ ] Verify all error states display correctly to user
- [ ] Verify chat source references are accurate
- [ ] Verify visual reels render correctly (image + video + fallback)
- [ ] Prepare demo document (pick a good 15–20 page PDF that produces quality reels)
- [ ] Write demo walkthrough script for Feb 23
- [ ] Final bug sweep and fix

**Day 3 Checkpoint:** App is production-ready on EC2. All features work including visual reels. Demo document and script ready.

---

## F9 — Visual Reels (Image & Video Backgrounds)

> Making reels visually engaging instead of plain text cards.

| Source | What | When used |
|--------|------|-----------|
| **Option A** — PDF image extraction | Extract images directly from the uploaded PDF using `pdfplumber` | When the PDF contains extractable images |
| **Option B** — Category illustrations | Pre-bundled static illustrations per topic (science, business, literature, tech, general) | Fallback when PDF has no images |
| **Option C** — Looping video clips | Pre-bundled short (~5-10s) looping background videos per category | **Visual learners only** (gated by `learning_style = 'visual'` from onboarding) |

**Fallback chain:** Option A (PDF image) → Option B (category illustration) → plain gradient background

**Schema addition needed:** `reels` table gets `media_url TEXT` and `media_type TEXT` (`'image'`, `'video'`, `NULL`) columns.

---

## EC2 Setup Checklist (Sakshi — completed)

```
1. [x] Launch EC2 (Ubuntu 24.04, 8 GB RAM) — IP: 72.62.231.169
2. [x] Security group: open ports 8000 (API + Frontend), 22 (SSH)
3. [x] Install Python, espeak-ng, git, curl (native setup, no Docker)
4. [x] Install Ollama natively as systemd service
5. [x] Pull models: ollama pull qwen2.5:3b && ollama pull nomic-embed-text
6. [x] Verify: curl http://localhost:11434/api/tags → both models listed
7. [x] Set OLLAMA_NUM_PARALLEL=1 via systemd override
8. [x] Git clone repo, backend running on port 8000
9. [x] Set up shared SSH access for all 3 engineers (Sanika + Esha added)
```

---

## Priority Order (if behind schedule)

1. **Must ship:** Upload/Parse → Reel Generation → Feed (F3, F4, F7)
2. **High:** Onboarding → Chat Q&A → Flashcards (F2, F6, F5)
3. **Medium:** Auth → Bookmarks → Download (F1, F8)
4. **Nice to have:** Visual Reels (F9), TTS audio, progress tracking
