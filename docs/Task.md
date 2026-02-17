# Verso - Task Breakdown

**Timeline:** 3 Days (Feb 16–18) | **Demo:** Feb 23
**Target:** EC2 `c6i.xlarge` (4 vCPU, 8 GB RAM, 20 GB gp3 EBS)
**Team:** 3 Full-Stack Engineers

---

## Engineer Assignments (Day 3 — Reshuffled)

| Engineer | Day 3 Role | Scope |
|----------|-----------|-------|
| **Sanika** | All Frontend + Bug Fixes | UI for My Books, feed interleaving, bookmarks wiring, download, profile, emoji display, reel rename, responsive polish |
| **Esha** | Prompts & AI Model Tuning | Prompt quality, emoji in prompts, pipeline edge cases, timeout handling, graceful degradation, TTS narration, RAM checks |
| **Sakshi** | Backend APIs + Pipeline Fixes | Bookmarks/progress/download APIs, feed interleaving, My Books data, profile API, 50-page limit, emoji schema, carry-over edge cases |

---

## Day 1 — Core Pipeline + UI Shell + RAG Engine ✅ COMPLETE

> All engineers SSH into EC2 from Day 1. Develop directly on the target machine. Ollama runs on EC2 throughout.

### Sakshi — Infra + Document Upload + Reel Generation Pipeline ✅
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

### Esha — Frontend Setup + All UI Pages ✅
- [x] Initialize React + Vite with Tailwind CSS 4.x, React Router 7.x, Zustand 5.x, Axios
- [x] Set up frontend project structure: pages, components, stores, API layer
- [x] Build main app layout/navigation shell (Feed, Flashcards, Bookmarks, Chat tabs)
- [x] Build Flashcards page — flip-card UI for self-testing, grouped by document
- [x] Build Chat Q&A page UI — message input, response display with source references, loading states
- [x] Build Progress tracking UI — viewing progress per upload
- [x] Implement bookmark toggle on reel cards and flashcards
- [x] Mobile responsiveness — swipe on touch, layout adapts
- [x] Build Document Upload page — drag & drop + file picker, file type/size validation (50 MB)
- [x] Build processing progress indicator — polling `/upload/status/{id}` every 3s
- [x] Build Swipeable Reel Feed using Swiper.js — full-screen vertical cards
- [x] Reel card component: title, summary, category badge, keywords, page ref, bookmark icon, audio button
- [x] Implement infinite scroll with paginated loading (auto-fetch 3 reels from end)
- [x] Incremental reel loading — new reels appear as batches complete
- [x] Build Bookmarks/Saved page — list of saved reels and flashcards

### Sanika — RAG Engine + TTS ✅
- [x] Build chunk embedding pipeline — `nomic-embed-text` via Ollama `/api/embed`
- [x] Build NumPy cosine similarity search (top-3 chunk retrieval)
- [x] Expose retrieval as internal function for chat endpoint to call
- [x] Implement TTS module — `espeak-ng` subprocess, `.wav` cached by content hash, `threading.Lock()`
- [x] Implement `/audio/{reel_id}` — serve cached audio or generate on-demand

**Day 1 Status: COMPLETE** — Full end-to-end backend flow tested: `/upload` → `/upload/status` → `/feed` → `/flashcards` all working.

---

## Day 2 — Onboarding → Chat → Auth → Wiring ✅ COMPLETE (behind target)

> **Build order matters:** Onboarding first (preferences stored), then Chat (reads preferences), then Auth (wraps everything).

### Sakshi — Pipeline Hardening + Audio (8 tasks incomplete — carried to Day 3)
- [x] Wire embedding trigger after all reel batches complete (hand off to RAG pipeline) — done by Esha
- [ ] ~~Handle edge cases: empty PDFs, scanned PDFs (< 50 chars detection), oversized files~~ → Day 3 (Sakshi + Esha)
- [ ] ~~Add timeout handling for Ollama calls (120–600s per call)~~ → Day 3 (Esha)
- [ ] ~~Tune LLM prompts for consistent JSON across doc types~~ → Day 3 (Esha)
- [ ] ~~Test graceful degradation: kill Ollama mid-process → verify fallback reels~~ → Day 3 (Esha)
- [ ] ~~RAM check — verify peak RAM < 6.5 GB during processing~~ → Day 3 (Esha)

### Esha — Onboarding Backend → Chat Backend → Frontend Wiring ✅ (1 remaining)
- [x] **F2:** Implement onboarding backend — `/onboarding/preferences` CRUD (save + retrieve user preferences)
- [x] **F2:** Onboarding stores: learning_style, content_depth, use_case, flashcard_difficulty
- [x] **F2:** Build Onboarding quiz UI — 5-step quiz (name, learning style, content depth, use case, flashcard difficulty) + confirmation screen
- [x] **F6:** Implement `/chat/ask` — embed question → RAG retrieval → preference-aware LLM answer
- [x] **F6:** Implement `/chat/history/{upload_id}`, `/chat/status/{upload_id}`
- [x] **F6:** Exchange limit per document (10/doc), `qa_ready` gating (409 if still processing)
- [x] Chat disabled state in UI when `qa_ready = false`
- [x] Wire feed to real API — remove mock data fallback, map API response fields
- [x] Fix feed scroll — one reel per swipe (Swiper mousewheel thresholds)
- [x] Wire `qa_ready` flag — pipeline sets `qa_ready = 1` after embedding completes
- [x] Switch frontend Dockerfile from `node:20-alpine` to `node:20-slim`
- [x] Audio playback on reel cards — play/pause button, GET `/audio/{reel_id}`
- [x] Loading states, error states, empty states across all pages — `StateScreens.jsx` component with `Spinner`, `ErrorState`, `EmptyState`
- [x] Wire Flashcards page to real `/flashcards` API (remove mock data)
- [x] Bookmarks page uses real store data (mock fallback removed)
- [x] Audio router fixed — real DB lookup, improved TTS voice + pitch/gap params
- [ ] ~~Build download button/flow in UI~~ → Day 3 (Sanika)

### Sanika — Auth + Feed/Bookmarks/Download APIs (3 tasks incomplete — carried to Day 3)
- [x] Implement `/auth/signup` and `/auth/login` — bcrypt hashing, token-based session
- [x] Implement `/auth/me` for session validation
- [x] Build Login/Signup UI pages
- [x] Wire auth flow: signup → login → onboarding → redirect to upload
- [x] Protected routes — redirect to login if unauthenticated
- [x] Implement `/feed` endpoint — paginated reel list from SQLite
- [x] Implement `/flashcards` endpoint — list by upload
- [ ] ~~Implement `/bookmarks` CRUD~~ → Day 3 (Sakshi)
- [ ] ~~Implement `/progress/view`~~ → Day 3 (Sakshi)
- [ ] ~~Implement `/download`~~ → Day 3 (Sakshi)

**Day 2 Status: 23/35 done (66%) — behind target.** Auth, onboarding, chat, feed, flashcards wired. Bookmarks/download/progress APIs, pipeline hardening, and download UI incomplete — carried to Day 3.

---

## User Flow Updates (Day 3)

These flow changes apply across Day 3 tasks:

1. **Feed interleaving:** After every 3 reels → 1 flashcard appears in the feed
2. **My Books:** New separate nav item showing uploaded books with reels/flashcards/chat per book
3. **Saved section:** Accessible from book detail and from main nav
4. **Download:** Reels only (no flashcards in download bundle)
5. **PDF upload limit:** 50 MB file size + 50 page cap (8 GB CPU constraint)
6. **User profile:** Lightweight — preferences tab + logout
7. **Rename "reels":** Find a different term across all UI (TBD by team)
8. **Emoji per reel:** Add topic-relevant emoji to each reel card

---

## Day 3 — New Features + Polish + Demo Prep (Feb 18)

> Roles reshuffled for Day 3. All Day 2 leftovers reassigned to new owners with clean ownership.

### Sakshi — Backend APIs + Pipeline Fixes
- [ ] Bookmarks CRUD: `POST /bookmarks`, `DELETE /bookmarks/{id}`, `GET /bookmarks` (DB table exists, no API yet)
- [ ] Progress tracking: `POST /progress/view`, `GET /progress/{upload_id}` (DB table exists, no API yet)
- [ ] Download: `GET /download/{upload_id}` — reels only, bundled as zip
- [ ] Update `/feed` to interleave flashcards (every 3 reels → 1 flashcard in response)
- [ ] Update `/uploads` response to include `reel_count` + `flashcard_count` per upload (for My Books page)
- [ ] User profile: `GET /profile`, `PUT /profile` (return preferences + user info)
- [ ] Enforce 50-page limit on upload (in addition to 50 MB file size)
- [ ] Add emoji field to reel DB schema + generation (update `prompts.py` and `llm.py` for emoji in reel output)
- [ ] Carry from Day 2: edge cases (empty/scanned PDFs), timeout handling, RAM check

### Sanika — All Frontend + Bug Fixes
- [ ] Wire bookmarks to real backend API (replace Zustand-only client-side bookmarks)
- [ ] Build "My Books" page — new nav item, list of uploads with reel/flashcard counts, tap into book detail (reels + flashcards + chat for that book)
- [ ] Update feed to render interleaved flashcards (every 3 reels → 1 flashcard card)
- [ ] Build download button on reel cards (reels only, hit backend `/download`)
- [ ] Build user profile page (view/edit preferences + logout) — lightweight, skip if heavy
- [ ] Display emoji on reel cards (from backend response)
- [ ] Rename "reels" to new term across all UI components and pages
- [ ] Wire progress page to real API (replace mock data)
- [ ] Bug fixes across all pages
- [ ] Final responsive pass (mobile + desktop)
- [ ] Carry from Day 2: download UI wiring

### Esha — Prompts & AI Model Tuning
- [ ] Add emoji field to reel generation prompts (topic-relevant emoji per reel)
- [ ] Tune prompts for consistent JSON output across all doc types (textbook, research, business, fiction, technical)
- [ ] Handle edge cases in pipeline: empty PDFs, scanned PDFs (<50 chars), oversized files
- [ ] Add/verify timeout handling for Ollama calls (120–600s)
- [ ] Test graceful degradation: kill Ollama mid-process → verify fallback reels
- [ ] Improve narration text quality for TTS (better speech-optimized output)
- [ ] Test with 5+ varied documents end-to-end
- [ ] RAM check: verify peak < 6.5 GB during processing

**Day 3 Checkpoint:** App is production-ready on EC2. All features work including new user flows. Demo document and script ready.

---

## Priority Order (updated Feb 18)

1. **Backend APIs for bookmarks/progress/download** (Sakshi) — unblocks frontend
2. **Feed interleaving + My Books** (Sakshi backend + Sanika frontend) — new user flow
3. **Prompt tuning + emoji** (Esha + Sakshi) — quality improvement
4. **User profile** (Sakshi backend + Sanika frontend) — lightweight, skip if time-tight
5. **Pipeline hardening + edge cases** (Esha) — robustness
6. **Bug fixes + polish** (Sanika) — demo readiness
7. **Rename reel term** (Sanika) — branding, do last

---

## GitHub Board — Open Issues (updated Feb 18)

| # | Issue | Owner | Label | Status |
|---|-------|-------|-------|--------|
| **#94** | Pipeline hardening — edge cases, timeouts, prompt tuning, degradation | **Esha** | Day 3 | **Reassigned** |
| **#64** | F9: Visual Reels — images & video backgrounds (deprioritized) | — | Backlog | Deprioritized |
| **#65** | Production hardening & performance benchmarks | **Esha** | Day 3 | Open |
| **#70** | Bookmarks, Download, Progress APIs (end-to-end) | **Sakshi** | Day 3 | **Reassigned** |
| **#71** | Regression testing & demo prep | **All** | Day 3 | Open |
| **#68** | Frontend polish + all UI wiring | **Sanika** | Day 3 | **Reassigned** |

---

## Audio Narration Improvements (Esha — Day 3)

- [ ] Improve narration text quality for TTS (speech-optimized output via prompt changes)
- [ ] Handle edge cases — very long text truncation (>500 chars), special characters breaking espeak-ng
- [ ] Test espeak-ng on EC2 — verify it's installed and working, test with real reels

---

## EC2 Setup Checklist (Sakshi — completed) ✅

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
