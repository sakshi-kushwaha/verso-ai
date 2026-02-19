# Verso AI — Multi-Model Routing Plan

## Architecture Overview

We're routing different tasks to specialized models to get better quality within 8GB RAM:

| Task | Model | Why |
|------|-------|-----|
| Classification (doc_type, subject) | `qwen3:0.6b` | Fast, lightweight, only needs single-word output |
| Reel generation (summaries, narration, flashcards) | `qwen3:4b` | Better quality JSON output, good narration |
| Chat Q&A (RAG) | `qwen3:4b` | Better conversational quality |
| Embeddings | `nomic-embed-text` | Unchanged, works well |

**Key constraint:** `OLLAMA_MAX_LOADED_MODELS=1` in docker-compose.yml — only one model in RAM at a time. Ollama auto-swaps models on demand (unloads current, loads requested).

---

## Completed Steps

### Step 1: Install models ✅
- `qwen3:0.6b` and `qwen3:4b` pulled into Docker Ollama
- Both tested via CLI and produce good output

### Step 2: Route classification to qwen3:0.6b ✅
**Branch:** `esha/classification-model`
**Files changed:**

**`backend/config.py`**
- Added `CLASSIFICATION_MODEL = "qwen3:0.6b"` (env-overridable)
- Added `REEL_MODEL = "qwen2.5:3b"` (placeholder, Step 3 changes this)
- Added `CHAT_MODEL = "qwen2.5:3b"` (placeholder, Step 5 changes this)

**`backend/llm.py`**
- Added `classification_llm_call(prompt)` — calls qwen3:0.6b with `/no_think` prefix, temperature 0.1, num_ctx 2048
- Added `clean_classification_response(text)` — strips `<think>...</think>` tags, extracts first word, lowercases it
- Updated `detect_doc_type()` and `detect_subject_category()` to use the new functions
- The existing `llm_call()` and `generate_reels()` are **untouched** — they still use qwen2.5:3b

**`backend/prompts.py`**
- Made both classification prompts more explicit: "Respond with ONLY a single category word from the list above. No explanation, no punctuation, just the word."

**Tested:** Uploaded a PDF, confirmed doc_type = "textbook" in DB, confirmed Ollama logs show qwen3:0.6b was used (not qwen2.5:3b).

---

## Remaining Steps

### Step 3: Route reel generation to qwen3:4b

**What to do:**
1. In `config.py`, change `REEL_MODEL` default to `"qwen3:4b"`
2. In `llm.py`, create a new `reel_llm_call(prompt)` function (similar to `classification_llm_call` but for reels):
   - Uses `REEL_MODEL` (qwen3:4b)
   - Adds `/no_think` prefix to the prompt
   - Uses `format: "json"` for structured output
   - Timeout should be 600s (model is slow on CPU)
3. **CRITICAL BUG TO HANDLE:** When qwen3:4b is called with `format: "json"`, it puts the JSON in the `thinking` field instead of the `response` field. The fix:
   ```python
   data = resp.json()
   result = data.get("response", "")
   if not result.strip() and data.get("thinking"):
       result = data["thinking"]
   return result
   ```
4. Update `generate_reels()` to call `reel_llm_call()` instead of `llm_call()`
5. The existing `parse_llm_json()` should work as-is since it already handles JSON extraction

**Test:** Upload a PDF, verify reels are generated, check Ollama logs confirm qwen3:4b was used.

**Performance note:** qwen3:4b takes ~60s per small chunk on CPU. A 10-page PDF may take 5-10 minutes. This is a tradeoff for better quality output.

---

### Step 4: Upgrade TTS voice quality

**What to do:**
1. Find a higher quality Piper voice model (current: `en_US-lessac-medium.onnx`)
2. Options to consider: `en_US-lessac-high.onnx` or `en_GB-alan-medium.onnx`
3. Download the new `.onnx` + `.onnx.json` files to `backend/tts/models/`
4. Update `PIPER_MODEL` in `config.py`
5. Clear audio cache (`data/audio_cache/`) and test with a reel

---

### Step 5: Route chat Q&A to qwen3:4b

**What to do:**
1. In `config.py`, change `CHAT_MODEL` default to `"qwen3:4b"`
2. Find the chat handler (likely in `routers/chat.py` or similar) that calls `llm_call()`
3. Create `chat_llm_call()` or reuse the reel one with `CHAT_MODEL`
4. Add `/no_think` prefix to chat prompts
5. Handle the `thinking` vs `response` field issue here too (same fix as Step 3)
6. Chat does NOT use `format: "json"`, so the thinking field bug may not apply — test both ways

**Test:** Upload a PDF, then ask a question in the chat. Verify answer quality and check Ollama logs.

---

### Step 6: Add video template selection system

**What to do:**
1. Add different visual templates/themes for reel videos
2. Template could be selected based on subject_category (science = blue/lab theme, arts = colorful, etc.)
3. May need frontend changes for different reel card layouts
4. Backend: add a `template` field to the reel data or determine it from category

---

### Step 7: Remove onboarding

**Status:** Already done on `main` via PR #111. Skip this step.

---

### Step 8: Add interaction tracking

**What to do:**
1. Create a new `interactions` table in the DB:
   ```sql
   CREATE TABLE interactions (
       id INTEGER PRIMARY KEY,
       user_id INTEGER,
       reel_id INTEGER,
       action TEXT,        -- 'view', 'swipe_up', 'swipe_down', 'flashcard_flip', 'chat_message', etc.
       duration_ms INTEGER,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```
2. Add a POST `/api/interactions` endpoint to log events
3. Frontend sends events on: reel view, swipe direction, time spent on reel, flashcard flip, chat open/message
4. This data feeds into Step 10 (feed algorithm)

---

### Step 9: Seed 100 platform reels

**What to do:**
1. Curate 100 educational reels across all subject categories
2. These are "platform reels" — not tied to any user upload
3. Could be generated from public domain educational texts
4. Add a `is_platform` flag to the reels table (or a special system user)
5. These appear in the feed for all users

---

### Step 10: Build feed algorithm

**What to do:**
1. Use interaction data (Step 8) to build a personalization model
2. Factors: subject preference (based on views), engagement (time spent), recency
3. Mix: user's own reels + platform reels (Step 9) + potentially other users' public reels
4. API endpoint: GET `/api/feed` that returns ranked reels for the current user
5. Frontend: replace current reel list with the feed

---

## Model Swap Flow (per PDF upload)

```
1. classify doc_type    → loads qwen3:0.6b (~2s)
2. classify subject     → qwen3:0.6b already loaded (~1s)
3. generate reels       → unloads 0.6b, loads qwen3:4b (~60s+ per chunk)
4. generate embeddings  → unloads 4b, loads nomic-embed-text (~5s)
5. (later) chat Q&A     → loads qwen3:4b on demand
```

## Environment

- **EC2:** 8GB RAM — peak usage must stay under 5.5GB
- **Docker Compose:** 3 services (backend, frontend, ollama)
- **OLLAMA_MAX_LOADED_MODELS=1** — one model in RAM at a time
- **Live reload:** backend volume-mounted, restart container to pick up changes
