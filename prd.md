# **Verso**

## Learn Smarter, Scroll Better

An AI-Powered App That Transforms Documents into Reels-Style Learning

**Local AI Hackathon — CPU-Only Edition**

**8 GB RAM | CPU-Only EC2 | No External AI APIs | Everything Local**

PRD Submitted: 15 February 2026

Build: 16–22 Feb | Demo: 23 Feb 2026

Team Size: 3

---

## **1. Problem Statement**

### **What problem are we solving?**

People of all ages struggle to engage with long-form educational and professional content like textbooks, research papers, and documents. Traditional reading is time-consuming, passive, and mentally draining — leading to poor retention. You either read the whole thing or miss important points, with no engaging format to help you along the way.

### **Who is the target user?**

Learners of all age groups — students, working professionals, and lifelong learners — who need to absorb knowledge from lengthy PDFs and documents, especially those who prefer bite-sized, scrollable content over dense, static pages.

### **Why does this problem matter?**

- People retain only ~10–20% of what they read passively, yet documents remain the primary way we share knowledge
- Short-form scrollable content has proven to be highly engaging, but there's no bridge between that experience and educational or professional material
- Existing tools either over-summarize (losing important details) or just highlight text (which is still passive and boring)
- Documents remain the default format across schools, colleges, and workplaces — yet the reading experience hasn't evolved in decades

> *Verso bridges this gap by transforming any PDF or Word document into swipeable, reels-style learning content with flashcards, personalized onboarding, and conversational Q&A — powered entirely by local AI. It works fully offline, keeps user data private, and makes studying feel like scrolling a feed.*

---

## **2. Proposed Solution**

### **What is Verso?**

Verso is a local-first, AI-powered web application that converts PDF and DOCX documents into a scrollable feed of short, swipeable learning reels. It runs entirely offline using a local AI backend, keeping all user data private.

### **What will it do?**

- Authenticated Experience — User login to maintain personalized profiles and progress across sessions
- Customized Onboarding — Detect user learning preferences (visual, auditory, reading) and adapt content style via an onboarding flow
- Document Parsing — Accept PDF and DOCX uploads and progressively parse them into sections, detecting document type automatically
- Static Reel Generation — Use a local AI model to produce structured text reels — titles, categorized summaries, keywords, and page references
- Flashcards + Reels — Generate flashcards alongside reels for active recall and self-testing
- Chat Conversation + Summary — Q&A chat over uploaded documents with conversation summaries saved for later
- Download & Save — Bookmark reels, save flashcards, and download content for offline use
- Progress Tracking — Track reading and viewing progress across uploads

### **What will it NOT do?**

- Does not support formats other than PDF and DOCX — no web links, videos, or ebooks
- Does not allow real-time collaboration or sharing with others
- Does not sync across devices — everything stays on your local machine
- Does not extract images or diagrams from documents — text content only
- Does not generate video or animated reels — reels are text-based with optional audio
- Does not guarantee 100% accuracy — content is AI-generated and may occasionally contain errors
- Does not require internet — runs fully offline with no cloud dependency

> *Scope Boundary: Verso is a learning and review tool, not a document editor or exam platform. It takes documents in and produces engaging reels, flashcards, and Q&A — nothing more.*

---

## **3. Core Features (MVP Only)**

| # | Feature | Description |
|---|---------|-------------|
| **F1** | **Authentication** | **Simple login/signup using name and password. Credentials stored locally. No email verification — just basic auth to tie preferences, progress, and bookmarks to a profile.** |
| **F2** | **Customized Onboarding** | **First-time users complete a short quiz capturing learning style (visual, auditory, reading) and content preferences. This profile drives how reels are generated — e.g., visual learners get structured bullet points, auditory learners get conversational narration scripts. Document type is auto-detected to further tailor content.** |
| **F3** | **Document Upload & Progressive Parsing** | **Upload a PDF or DOCX (max 50 MB) and parse it progressively in batches of 5 pages using pdfplumber (PDF) or python-docx (DOCX). Processing runs in the background so the UI stays responsive, with reels appearing incrementally as batches complete.** |
| **F4** | **Static Reel Generation** | **Each parsed batch is sent to a local LLM (Qwen 2.5 3B via Ollama) to extract key ideas and produce structured text reels — title, summary, topic category, keywords, and page reference. Reel count scales with document length (~1 reel per 4 pages). Prompts adapt based on learning style.** |
| **F5** | **Flashcards + Reels** | **Alongside each reel, the LLM generates flashcards (question/answer pairs) for active recall. Users swipe reels for passive learning and flip to flashcard mode for self-testing from a dedicated tab.** |
| **F6** | **Chat Conversation (Limited) + Summary** | **After parsing, users ask questions about the document via chat. Chunks are embedded locally (nomic-embed-text) and answers retrieved via semantic search RAG. Conversations are limited in length and summaries are saved for later.** |
| **F7** | **Swipeable Feed UI** | **Reels displayed in a full-screen vertical swipeable feed using Swiper.js. Each reel shows title, summary, category badge, page reference, and audio play button. Paginated loading with infinite scroll.** |
| **F8** | **Download & Save** | **Bookmark any reel or flashcard for later review (Saved tab). Download content as bundled offline packages. Audio narration via espeak-ng TTS is cached by content hash.** |

> *Design Principle: Verso generates reels progressively — users start consuming content within seconds of uploading, not after the entire document is processed. Every feature works offline with zero cloud dependency.*

---

## **4. AI Architecture Overview**

### **Models**

| Component | Model | Why This Choice |
|-----------|-------|-----------------|
| **LLM (Primary)** | **qwen2.5:3b** | **Best instruction-following and JSON output at the 3B class — outperforms Phi-3 and Gemma-2B. Q4 quantization reduces memory ~4x vs FP16. A 7B model would risk OOM. Expected: 5–15 tokens/sec on CPU. Context: 4096 tokens, input capped at ~3,000 chars/batch.** |
| | **Q4 quantization** | |
| | **~1.9 GB disk, ~3.0–3.5 GB RAM** | |
| **Embedding** | **nomic-embed-text** | **Purpose-built for retrieval, 768-dim vectors. Lightweight enough to co-exist with LLM. No vector DB needed — NumPy cosine similarity is instant at this scale.** |
| | **~274 MB disk, ~0.4 GB RAM** | |
| **TTS** | **espeak-ng** | **Rule-based, near-instant (~1–2 sec/reel), zero memory. AI TTS (Bark, Piper) needs 1–4 GB extra — exceeds budget. Robotic voice acceptable for MVP where audio is supplementary.** |
| | **~2 MB, ~0 RAM** | |
| **STT** | **N/A** | **Not applicable** |
| **Vision** | **N/A** | **Not applicable** |

### **Why a 3B model?**

| Model | Q4 Size | Fits 8 GB? | Verdict |
|-------|---------|------------|---------|
| **qwen2.5:3b (chosen)** | **~1.9 GB** | **Yes, comfortable** | **Best balance of quality and size** |
| **Phi-3 Mini 3.8B** | **~2.4 GB** | **Yes** | **Slightly weaker structured output** |
| **Llama 3.2 3B** | **~2.0 GB** | **Yes** | **Worse JSON adherence** |
| **DeepSeek-R1-Distill 7B** | **~4.6 GB** | **Barely** | **OOM risk** |
| **Mistral 7B** | **~4.5 GB** | **Barely** | **Same OOM risk** |

### **Tooling and Agent Logic**

We do NOT use any agent framework (no LangChain, no LangGraph). On 8 GB CPU, frameworks add memory overhead and unpredictable behavior. Instead, we build a structured linear pipeline in plain Python.

Pipeline per feature: Each AI feature is a simple sequential function:

- Step 1: Parse uploaded document into text batches
- Step 2: Detect document type (educational, technical, fiction, business)
- Step 3: Build structured prompt from template + user learning style
- Step 4: Single LLM inference call — one shot, no loops, no chaining
- Step 5: Parse JSON output, save reels + flashcards to SQLite, generate TTS audio

This keeps latency predictable and avoids runaway inference costs on CPU.

### **Memory Budget (8 GB)**

| Component | Est. RAM | Notes |
|-----------|----------|-------|
| **OS + Docker** | **~2.0 GB** | **Base system processes** |
| **Ollama + Qwen 2.5 3B (Q4)** | **~3.5 GB** | **Loaded on first LLM call, stays warm** |
| **Ollama + nomic-embed-text** | **~0.4 GB** | **Loaded for RAG, auto-unloaded when idle** |
| **FastAPI + Python + pdfplumber** | **~0.3 GB** | **Web server + document parsing** |
| **React (production build)** | **~0.1 GB** | **Static files, minimal footprint** |
| **NumPy + RAG index + SQLite** | **~0.1 GB** | **Vector math + persistence** |
| **TOTAL USED** | **~6.4 GB** | |
| **FREE HEADROOM** | **~1.6 GB** | **Safety margin for spikes** |

> *Key: Ollama auto-unloads idle models after 5 min. LLM and embedding model are used in different stages — they rarely coexist in memory, giving additional headroom.*

### **Expected Latency**

| Feature | Latency | Why |
|---------|---------|-----|
| **Document parsing (50 pages)** | **~2–3 seconds** | **pdfplumber/python-docx text extraction** |
| **Doc type detection** | **~10–40 seconds** | **Single LLM call on first batch** |
| **Reel + flashcard generation (per batch)** | **~15–45 seconds** | **LLM inference on CPU** |
| **Embedding per chunk** | **~50ms–3 seconds** | **Lightweight embedding model** |
| **TTS per reel** | **~1–2 seconds** | **OS-native espeak-ng, cached on disk** |
| **Full 20-page document → ~5 reels** | **~2–4 minutes total** | **Background processing, progressive delivery** |
| **Chat Q&A response** | **~15–30 seconds** | **Embed + retrieve + LLM answer** |

> *Key design: Reel generation runs in background threads. Users see a progress indicator and reels appear incrementally — no waiting for the full document to finish.*

---

## **5. System Architecture**

### **End-to-End Architecture**

```
+----------------------- FRONTEND (React + Vite, :3000) -----------------------+
|  Login/Signup -> Onboarding -> Upload Doc -> Reel Feed (Swiper) -> Chat Q&A  |
|  Bookmarks Page  |  Flashcards Page  |  Progress Page  |  Download           |
+----------------------------------  Axios HTTP  ------------------------------+
                                      |
                                      v
+----------------------- BACKEND (FastAPI + Uvicorn, :8000) -------------------+
|  API: /auth  /upload  /feed  /bookmarks  /flashcards  /chat  /download       |
|  +-----------------+  +-------------------+  +------------------+            |
|  | Document Parser |  | Background Thread |  | RAG Engine       |            |
|  | pdfplumber /    |  | reel + flashcard  |  | (NumPy cosine)   |            |
|  | python-docx     |  | generation        |  |                  |            |
|  +-----------------+  +---------+---------+  +--------+---------+            |
|  +-----------------+            |                      |                     |
|  | SQLite (verso.db)|           |     +----------------+                     |
|  | Users, reels,    |           |     |  +------------------+                |
|  | flashcards,      |           |     |  | TTS: espeak-ng   |                |
|  | bookmarks, chat  |           |     |  | Audio -> disk    |                |
|  +-----------------+            |     |  +------------------+                |
+-------------------------------+-+-----+--------------------------------------+
                                |       |
                                v       v
+----------------------- OLLAMA CONTAINER (:11434) ----------------------------+
|  qwen2.5:3b (~3.5 GB)    <->    nomic-embed-text (~0.4 GB)                  |
|  POST /api/chat                 POST /api/embed                              |
+------------------------------------------------------------------------------+
```

### **Flow 1: Authentication & Onboarding**

- **[1]** User opens app → Login/Signup page
- **[2]** POST /auth/signup {name, password} → hashed in SQLite → user_id returned
- **[3]** Onboarding Quiz: learning style (visual/auditory/reading) + preferences
- **[4]** Saved to user_preferences table → drives all LLM prompt templates
- **[5]** Redirect to Upload page

### **Flow 2: Document Upload → Reel + Flashcard Generation**

- **[1]** User selects PDF/DOCX → POST /upload (multipart, max 50 MB)
- **[2]** Save to temp file → pdfplumber or python-docx extracts text page-by-page
- **[3]** Detect chapter boundaries via regex (fallback: 3,000-char chunks)
- **[4]** Cap sections: max_sections = total_pages / 4
- **[5]** Insert upload record to SQLite (status: 'processing'), return upload_id immediately
- **[6]** BACKGROUND: First batch → doc type detection (2,000 chars → Qwen 2.5 3B)
- **[7]** FOR EACH BATCH (5 pages): 3,000 chars + learning-style prompt → LLM → JSON reels + flashcards
- **[8]** Each reel narration → espeak-ng → .wav cached by content hash on disk
- **[9]** Save reels + flashcards to SQLite, update progress count
- **[10]** After all batches: embed chunks → nomic-embed-text → NumPy array for RAG
- **[11]** Mark status = 'done', qa_ready = true. Delete temp file.

Frontend polls GET /upload/status/{id} every 3 seconds. Reels appear incrementally as each batch completes.

### **Flow 3: Feed Consumption**

- **[1]** GET /feed → paginated reel list from SQLite
- **[2]** Swiper.js renders vertical full-screen reel cards
- **[3]** On swipe → POST /progress/view (tracks viewed reels)
- **[4]** Infinite scroll: auto-fetch next page when 3 reels from end
- **[5]** Audio: GET /audio/{reel_id} → serve cached .wav or generate on-demand

### **Flow 4: Chat Q&A (Limited) + Summary**

- **[1]** POST /chat/ask {question} (enabled after qa_ready = true)
- **[2]** Embed question → nomic-embed-text → 768-dim vector
- **[3]** Cosine similarity against document chunks → top-3 matches
- **[4]** Question + retrieved chunks → Qwen 2.5 3B → grounded answer
- **[5]** Return answer with source references. Save exchange to SQLite.
- **[6]** Limited to N exchanges per document. Summary generated and cached on demand.

### **Flow 5: Bookmarks, Flashcards & Download**

- Bookmark: tap icon → saved. View from Bookmarks page.
- Flashcards: flip-card UI for self-testing from dedicated tab.
- Download: bundled reels + flashcards + audio as zip package.

### **Model Calls Summary (for N-page document)**

| Phase | Call Type | Count |
|-------|-----------|-------|
| **Doc type detection** | **LLM (qwen2.5:3b)** | **1 call** |
| **Reel + flashcard extraction** | **LLM (qwen2.5:3b)** | **ceil(N/5) calls** |
| **TTS audio generation** | **espeak-ng CLI** | **~ceil(N/5) calls** |
| **Chunk embedding** | **nomic-embed-text** | **ceil(N/5) calls** |
| **Chat Q&A (per question)** | **1 embed + 1 LLM** | **On-demand** |
| **Chat summary** | **LLM (qwen2.5:3b)** | **On-demand** |

### **Data Storage Layout**

```
data/
  |-- verso.db              # Users, uploads, reels, flashcards,
  |                         # bookmarks, progress, chat_history
  |-- audio_cache/          # Generated .wav files (by content hash)
  +-- temp/                 # Temp uploads (cleaned after parse)
```

---

## **6. Memory and Resource Strategy**

### **How We Avoid Running Out of RAM**

| Strategy | Implementation |
|----------|---------------|
| **Small quantized models** | **Qwen 2.5 3B Q4 (~3.5 GB) + nomic-embed-text (~0.4 GB). Together under 4 GB. A 7B model would risk OOM.** |
| **Capped input sizes** | **Doc detection: 2,000 chars. Extraction: 3,000 chars. Embedding: 500 chars/chunk. Prevents KV cache blowup.** |
| **Fixed context window** | **4096 tokens. KV cache = ~144 MB (72 MB K + 72 MB V). Single biggest memory guard.** |
| **Documents streamed page-by-page** | **pdfplumber/python-docx per-page. Full file binary never held in memory.** |
| **Upload size limit** | **50 MB max prevents OOM from large file reads.** |
| **Audio on disk, not RAM** | **espeak-ng writes .wav to disk. Served as static files. Never buffered in Python.** |
| **Temp file cleanup** | **Uploads deleted after parsing via os.unlink() in try/finally.** |
| **Lightweight data** | **Each reel ~1 KB. 70-page doc totals ~154 KB. Negligible.** |
| **SQLite persistence** | **No in-memory session dicts. All data in SQLite. Only active requests in RAM.** |
| **Section cap** | **total_pages / 4 limits LLM calls and accumulated results per upload.** |

### **Model Loading Strategy**

Ollama handles model lifecycle automatically. On app start, models are on disk only. First LLM call loads Qwen 2.5 3B (~14s cold start). Model stays warm for subsequent calls. After all batches, embedding triggers nomic-embed-text load (~0.4 GB). If RAM is tight, Ollama may auto-unload Qwen first. After 5 min idle, unused models are freed.

Key point: LLM and embedding model are used in different workflow stages and never run simultaneously. Even worst case (both loaded = ~3.9 GB for models) stays within budget.

### **Concurrency Handling**

Designed for single-user, sequential operation:

| Component | Model | Protection |
|-----------|-------|------------|
| **Reel generation** | **Single background thread** | **Second upload queues behind first in Ollama** |
| **TTS engine** | **Thread-locked** | **threading.Lock() prevents concurrent espeak-ng** |
| **Ollama** | **Serialized (NUM_PARALLEL=1)** | **Queues requests, no parallel CPU inference** |
| **SQLite** | **Single-writer** | **get_db() context manager per-request** |
| **FastAPI** | **Async event loop** | **Heavy work offloaded to background thread** |

### **Crash Prevention & Graceful Degradation**

| Failure Mode | Prevention | Recovery |
|-------------|------------|----------|
| **Ollama OOM** | **httpx timeouts. Context capped at 4096 tokens.** | **Section skipped. Docker restart policy.** |
| **Bad LLM JSON** | **Defensive JSON parsing with fallback** | **Fallback reel with raw text. Continues.** |
| **TTS fails** | **try/except wrapper** | **Reel saved without audio.** |
| **Document parse fails** | **try/finally cleanup** | **HTTP 500 with error message.** |
| **Disk full** | **Audio gen fails gracefully** | **Reel saved without audio.** |
| **Thread dies** | **Daemon + layered try/except** | **parsing_complete always set.** |
| **Container crash** | **Docker restart: unless-stopped** | **Auto-restart. In-progress lost.** |

Degradation chain: Best case: Reel + Flashcard + Audio → Fallback 1: No audio → Fallback 2: Reel skipped → Fallback 3: Upload error. No single failure crashes the app.

---

## **7. Technical Stack**

| Layer | Technology |
|-------|-----------|
| **Language (Frontend)** | **JavaScript (JSX), ES2022+** |
| **UI Framework** | **React 19.x + Vite** |
| **Styling** | **Tailwind CSS 4.x** |
| **Routing** | **React Router DOM 7.x** |
| **State Management** | **Zustand 5.x** |
| **HTTP Client** | **Axios** |
| **Swipe / Carousel** | **Swiper.js** |
| **Language (Backend)** | **Python 3.11+** |
| **Web Framework** | **FastAPI + Uvicorn (ASGI)** |
| **HTTP Client (internal)** | **httpx (for Ollama API calls)** |
| **PDF Parsing** | **pdfplumber (page-by-page extraction)** |
| **DOCX Parsing** | **python-docx (paragraph extraction)** |
| **Numerical Computing** | **NumPy (cosine similarity for RAG)** |
| **Validation** | **Pydantic (request/response schemas)** |
| **Database** | **SQLite3 (built-in, zero config)** |
| **LLM Runtime** | **Ollama (wraps llama.cpp, HTTP API on :11434)** |
| **Chat Model** | **Qwen 2.5 3B, Q4 quantization via Ollama** |
| **Embedding Model** | **nomic-embed-text (768-dim vectors)** |
| **TTS** | **espeak-ng (CLI subprocess, zero memory)** |
| **Vector Search** | **NumPy dot product (no vector DB at this scale)** |
| **Containerization** | **Docker Compose (multi-container orchestration)** |
| **Process Manager** | **systemd (no extra overhead)** |

### **Why Ollama Over Alternatives**

| Alternative | Why Not |
|------------|---------|
| **llama.cpp (direct)** | **Manual model management, no auto-unload. Ollama wraps it cleanly.** |
| **ONNX Runtime** | **No easy model switching or built-in registry.** |
| **vLLM** | **GPU-focused. No benefit on CPU-only.** |
| **LM Studio** | **GUI-focused. Not for headless Docker API serving.** |

### **EC2 Instance Type**

Primary recommendation: c6i.xlarge — 4 vCPUs, 8 GB RAM, ~$0.17/hr. Compute-optimized with no burst throttling — critical for sustained LLM inference. 20 GB gp3 EBS for models + cache.

| Instance | RAM | Why / Why Not |
|----------|-----|--------------|
| **t3.medium (4 GB)** | **4 GB** | **Not enough — model alone needs 3.5 GB** |
| **t3.large** | **8 GB** | **Fits but burstable CPU throttles on sustained LLM inference** |
| **c6i.xlarge (chosen)** | **8 GB** | **Compute-optimized. No burst throttling. Best for sustained Ollama calls.** |
| **t3.xlarge** | **16 GB** | **Overkill for MVP, doubles cost, exceeds 8 GB constraint** |

---

## **8. Evaluation Criteria**

### **Performance Metrics**

| Metric | Target | How Measured |
|--------|--------|-------------|
| **Document parse time** | **< 5 seconds (50 pages)** | **Timestamp logs** |
| **Time to first reel** | **< 90 seconds from upload** | **Upload → first reel in feed** |
| **Reel generation** | **< 30 sec per section** | **Ollama request/response timestamps** |
| **End-to-end (20-page doc)** | **< 3 minutes** | **Upload start → status 'done'** |
| **Feed load time** | **< 500ms** | **Network tab, GET /feed** |
| **Chat Q&A response** | **< 60 seconds** | **Question → answer displayed** |
| **TTS per reel** | **< 3 seconds** | **generate_audio timestamps** |
| **App startup** | **< 5 seconds** | **/health returns 200** |

### **Resource Metrics**

| Metric | Target | How Measured |
|--------|--------|-------------|
| **Peak RAM (processing)** | **< 6.5 GB** | **docker stats during processing** |
| **Idle RAM (unloaded)** | **< 3 GB** | **After Ollama 5-min auto-unload** |
| **Disk per reel (audio)** | **< 2 MB (.wav)** | **du -sh audio_cache/** |
| **SQLite DB** | **< 50 MB / 500 reels** | **ls -lh verso.db** |

### **Quality Metrics**

| Metric | Target | How Measured |
|--------|--------|-------------|
| **Reel gen success** | **> 90% valid reels** | **Log skipped vs total** |
| **JSON parse success** | **> 90%** | **Log failures vs total calls** |
| **Content relevance** | **Reflects source text** | **Manual spot-check 10 reels** |
| **Flashcard quality** | **Accurate Q&A pairs** | **Manual spot-check** |
| **TTS success** | **> 95% have audio** | **SQL: audio_path IS NOT NULL** |
| **RAG Q&A relevance** | **Top-3 chunks correct** | **Manual: 5 questions/doc** |

### **Robustness & User Experience**

| Metric | Target | How Measured |
|--------|--------|-------------|
| **Pipeline completion** | **100% never hangs** | **5 documents all reach complete** |
| **Graceful LLM failure** | **Fallback reel, continues** | **Kill Ollama mid-process** |
| **Scanned PDF handling** | **No crash, feedback** | **Upload image-only PDF** |
| **Onboarding time** | **< 30 seconds** | **First load → upload screen** |
| **Progress feedback** | **Within 10 seconds** | **Indicator before first reel** |
| **Feed smoothness** | **No jank on swipe** | **Chrome DevTools frames** |
| **Mobile usability** | **Swipe works on touch** | **Mobile browser test** |

---

## **9. Risks and Trade-offs**

### **Known Limitations**

| Limitation | Impact | Why Accepted |
|-----------|--------|-------------|
| **CPU-only inference** | **2–4 min per 20-page document** | **GPU would 10x the cost. Background processing is acceptable for MVP.** |
| **Robotic TTS voice** | **Audio sounds less natural** | **Natural-sounding AI voice models need 1–4 GB extra memory that we don't have. Audio is supplementary.** |
| **No OCR support** | **Scanned documents produce empty reels** | **Text extraction only. Documents with < 50 chars of text are auto-skipped.** |
| **English-optimized** | **Other languages may give lower quality** | **Prompts and TTS are tuned for English. The AI model supports other languages but quality varies.** |
| **Simple login** | **Not production-grade security** | **Acceptable for a local-first hackathon MVP. No sensitive data stored.** |
| **Fixed reel format** | **Every reel looks the same** | **Keeps the AI prompt simple and output consistent for the MVP.** |

### **Potential Failure Points**

| Failure | Likelihood | Mitigation |
|---------|-----------|-----------|
| **AI model runs out of memory** | **Medium** | **Context limited to 4096 tokens. Input text truncated. Docker auto-restarts.** |
| **AI takes too long to respond** | **Medium** | **120–600 second timeout. Each batch handled independently.** |
| **AI returns badly formatted output** | **Medium** | **Smart parsing with multi-level fallback. Bad sections skipped, others continue.** |
| **Upload gets stuck processing** | **Medium** | **Multiple safety layers. Users can re-upload.** |
| **Very large document (500+ pages)** | **Low** | **50 MB limit. Section cap controls total processing.** |
| **Multiple uploads at once** | **Low** | **AI processes one at a time. No crash, just slower.** |
| **Disk fills with audio files** | **Low** | **Reels saved without audio. Manual cleanup.** |

### **Trade-offs Made**

| Decision | What We Gave Up | Why |
|----------|----------------|-----|
| **Ollama over llama.cpp** | **~10–15% raw speed** | **Much simpler to manage, auto model loading/unloading** |
| **espeak-ng over AI voice** | **Natural voice quality** | **Saves 2–4 GB of memory. Non-negotiable on 8 GB.** |
| **SQLite over PostgreSQL** | **Multi-user support** | **Single-user app. Zero setup. No extra memory.** |
| **NumPy over vector database** | **Scalability** | **500 items searched in < 1ms. No need for complexity.** |
| **Q4 quantization** | **~5–10% quality** | **Necessary to fit the 3B model in ~3.5 GB RAM.** |
| **3B model over 7B** | **Content quality** | **7B model = ~5 GB memory, risks crashing.** |
| **No streaming output** | **Real-time preview** | **Background generation is simpler and more reliable.** |

### **What We'd Improve With More Resources**

| Resource | Improvement | Impact |
|----------|-----------|--------|
| **16 GB RAM** | **Upgrade to Qwen 2.5 7B** | **Better content quality + fewer formatting errors** |
| **16 GB RAM** | **Add natural-sounding AI voice** | **Much better audio narration experience** |
| **GPU (6+ GB)** | **10–100x faster processing** | **Reels generated in seconds, not minutes** |
| **GPU + 24 GB** | **Add image understanding** | **Extract diagrams and charts from documents** |
| **More dev time** | **Real-time push updates** | **Replace polling with instant delivery** |
| **More dev time** | **Resume interrupted processing** | **Survive app restarts mid-document** |
| **+500 MB RAM** | **OCR for scanned documents** | **Support image-based PDFs** |

---

## **10. Stretch Goals (Optional)**

These will only be attempted if F1–F8 are complete and stable by Day 5 of build week.

| # | Stretch Goal |
|---|-------------|
| **S1** | **Spaced Repetition — Remember what you learn by having Verso resurface reels and flashcards at the right time, helping you retain knowledge long-term instead of forgetting it after one read.** |
| **S2** | **Smart Reel Ordering — Learn what matters to you first. Verso reorders reels based on what you've bookmarked, skipped, or spent time on, so the most relevant content always comes first.** |
| **S3** | **Smarter Section Splitting — Better handling of documents that don't have clear chapter headings, so reels break at natural points instead of cutting off mid-sentence.** |
| **S4** | **Better Voice Narration — Replace the robotic voice with a more natural-sounding narrator, making it easier and more pleasant to listen to reels passively.** |
| **S5** | **Document Library — Upload multiple documents and browse a personal library of past uploads, so you can revisit any material anytime.** |
| **S6** | **Export & Share — Export your saved reels and flashcards as a study summary you can print, share, or review outside the app.** |
| **S7** | **More File Formats — Support for EPUB and plain text files in addition to PDF and DOCX.** |
| **S8** | **Image Extraction — Display figures, charts, and diagrams from your documents directly on reel cards alongside the text summaries.** |
| **S9** | **Voice Q&A — Ask questions about your document by speaking instead of typing, and hear the answers read back to you like a study companion.** |

---

> *Verso is not just a summarizer. It's a new way to learn from any document — one reel at a time. Every feature is designed around real learning science, real device constraints, and real user behavior. The demo will show real documents transformed into real reels with real AI — not a mockup.*
