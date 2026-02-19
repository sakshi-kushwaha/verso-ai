# Self-Learning Pipeline for Reel Generation

The reel generation model (qwen2.5:1.5b) follows prompt rules inconsistently — contractions, pauses, conversational starters, and word count targets are often ignored. There's no feedback loop: reels are generated once and never evaluated. This plan adds a closed-loop self-learning pipeline: **score reels → identify weaknesses → fix prompts → generate gold training data → fine-tune → deploy → repeat**.

The codebase already has evaluation infrastructure (`evals.py`, `eval_fixtures.py`), training data generation (`scripts/generate_training_data.py`), ShareGPT conversion (`scripts/convert_to_sharegpt.py`), and a Colab fine-tuning notebook (`scripts/verso_finetune.ipynb`). This plan extends and connects these existing pieces.

---

## Team Split — Two Members Working in Parallel

### Member A: Backend Core (Phases 0, 1, 2, 3)

**Branch:** `self-learning-backend`
**Touches:** Existing backend files only (`database.py`, `pipeline.py`, `evals.py`, `prompts.py`, `llm.py`) + 2 new scripts
**No merge conflicts with Member B** — Member B only creates new files in `scripts/`

| Task | Files | Effort |
|------|-------|--------|
| Phase 0: Save source_text | `backend/database.py`, `backend/pipeline.py` | Small |
| Phase 1: Narration scorer | `backend/evals.py`, NEW `scripts/score_reels.py` | Medium |
| Phase 2: System prompt + LLM wiring | `backend/prompts.py`, `backend/llm.py` | Small |
| Phase 3: A/B prompt compare | NEW `scripts/ab_compare.py` | Medium |

**Member A delivers:** The scoring infrastructure and prompt improvements. After merging, the production pipeline saves source_text and uses improved prompts.

---

### Member B: Scripts & Training Pipeline (Phases 4, 5, 6, 7, 8, 9)

**Branch:** `self-learning-training`
**Touches:** Only NEW files in `scripts/` + modify existing notebook
**No merge conflicts with Member A** — all new files

| Task | Files | Effort |
|------|-------|--------|
| Phase 4: Best-of-N generator | NEW `scripts/best_of_n_generate.py` | Medium |
| Phase 5: ShareGPT v2 converter | NEW `scripts/convert_gold_to_sharegpt.py` | Small |
| Phase 6: Update Colab notebook | `scripts/verso_finetune.ipynb` | Small |
| Phase 7: Modelfile v2 | NEW `scripts/Modelfile.v2` | Small |
| Phase 8: A/B model eval | NEW `scripts/ab_eval_models.py` | Medium |
| Phase 9: Orchestrator | NEW `scripts/self_learning_loop.sh` | Small |

**Member B delivers:** The full training-to-deployment pipeline. Scripts can be written and tested independently — they import from `backend/evals.py` (Member A's `score_reel()`) but can stub it during development.

---

### Coordination Points

1. **Interface contract:** Member B imports `score_reel(reel_dict, source_text, prefs)` from `backend/evals.py`. Member A must define this function signature first (even as a stub) so Member B can code against it.
2. **Merge order:** Member A merges first (backend changes), then Member B merges (scripts only, no conflicts).
3. **Both can start immediately:** Member B can write all scripts using a local `score_reel` stub that returns a dummy score, then swap to the real import after Member A merges.

### Stub Contract for Member B

Member B can start immediately using this stub in their scripts while Member A builds the real scorer:

```python
# Temporary stub — replace with: from evals import score_reel
def score_reel(reel_dict: dict, source_text: str, prefs: dict = None) -> dict:
    """Stub. Returns dummy score. Real version comes from backend/evals.py."""
    return {"composite_score": 0.5, "metrics": {}}
```

Once Member A pushes `score_reel()` to `backend/evals.py`, Member B replaces the stub with:
```python
from evals import score_reel
```

---

## Phase 0 — Save Source Text (Member A)

**Why:** Without source text stored alongside reels, we can't build training pairs or score content quality retroactively.

### `backend/database.py` (~line 132, after video_path migration)

Add migration following the existing pattern:

```python
# Migration: add source_text to reels
if "source_text" not in reel_cols:
    conn.execute("ALTER TABLE reels ADD COLUMN source_text TEXT")
```

### `backend/pipeline.py`

**`_save_reel()`** (line 333): Add `source_text` parameter and 9th placeholder in INSERT:

```python
def _save_reel(upload_id: int, reel: dict, page_ref: int, bg_image: str = None, source_text: str = "") -> int:
    conn = get_db()
    conn.execute(
        "INSERT INTO reels (upload_id, title, summary, narration, category, keywords, page_ref, bg_image, source_text) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (upload_id, reel.get("title", ""), reel.get("summary", ""),
         reel.get("narration", ""), reel.get("category", ""),
         reel.get("keywords", ""), page_ref, bg_image,
         (source_text or "")[:5000]),  # cap at 5KB per reel
    )
    conn.commit()
    reel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return reel_id
```

**Generation loop** (line 202): Pass `batch_text` through:

```python
reel_id = _save_reel(upload_id, reel, batch[0].get("start_page", i + 1), bg_image, source_text=batch_text)
```

---

## Phase 1 — Narration Quality Scorer (Member A)

**Why:** The existing 6 metrics in `evals.py` check JSON validity, schema, depth, style, content quality, and flashcard quality — but none check the specific narration rules from `REEL_GENERATION_PROMPT` (contractions, pauses, word count, hooks, no-textbook-language).

### `backend/evals.py` — Add two new functions

**`metric_narration_quality(parsed, **_)`** — Checks per-reel:
- Word count in 40-70 range
- Has at least 1 contraction (don't, isn't, you're, it's, here's, can't, won't, doesn't)
- Has conversational starter (here's the thing, think about, now, so)
- No passive voice in first sentence
- Uses pause markers (... or —)
- No textbook phrases (is defined as, plays a crucial role, furthermore, moreover, etc.)
- Sentence length variety (has both short ≤8 words and long ≥12 words)
- Returns `(float 0-1, details dict)`

**`score_reel(reel_dict, source_text, prefs)`** — Composite scorer wrapping all 7 metrics:
- Calls existing `metric_json_valid`, `metric_schema_complete`, `metric_depth_match`, `metric_style_match`, `metric_content_quality`, `metric_flashcard_quality`
- Calls new `metric_narration_quality`
- Returns `{"composite_score": float, "metrics": {name: {score, pass, weight}}}`
- Weights: content_quality and narration_quality get 1.5x, rest 1.0x

### `scripts/score_reels.py` — NEW CLI script

```
Usage:
    cd backend && python ../scripts/score_reels.py
    cd backend && python ../scripts/score_reels.py --export scores.jsonl
```

- Connects to DB, loads all reels, runs `score_reel()` on each
- Reports: average composite score, per-metric failure rates, top 25% and bottom 25% reels
- `--export scores.jsonl` option for downstream use
- Reuses pattern from existing `scripts/generate_training_data.py`

---

## Phase 2 — Targeted Prompt Fix (Member A)

**Why:** Rules buried deep in a long user prompt get diluted. Moving the most-violated rules into the system prompt (Ollama `system` field) gives them higher attention weight.

### `backend/prompts.py` — Add `REEL_SYSTEM_PROMPT`

```python
REEL_SYSTEM_PROMPT = """You are Verso, a learning content creator who teaches through short reels.
You are NOT a textbook. You explain like a friend.

CRITICAL RULES YOU MUST FOLLOW:
1. Use at least 3 contractions (don't, isn't, you're, it's, here's) in every narration.
2. Use "..." at least once and "—" at least once in every narration.
3. NEVER use: "is defined as", "refers to the process", "plays a crucial role",
   "it is important to note", "furthermore", "moreover".
4. Narration must be 40-60 words exactly.
5. Always output valid JSON with "reels" and "flashcards" arrays."""
```

> The exact rules to promote will be determined by Phase 1 scoring results — the 3 lowest-scoring metrics get promoted.

### `backend/llm.py`

- `reel_llm_call()` (line 125): Add `system: str = None` param, add `payload["system"] = system` when provided
- `generate_reels()` (line 228): Pass `system=REEL_SYSTEM_PROMPT` to `reel_llm_call()`

### `backend/prompts.py` — Slim down `REEL_GENERATION_PROMPT`

- Remove rules that are now in `REEL_SYSTEM_PROMPT` to avoid token waste
- Keep: JSON schema, doc_type/style/depth/use_case/difficulty instructions, few-shot example

---

## Phase 3 — A/B Compare Prompt Changes (Member A)

### `scripts/ab_compare.py` — NEW script

```
Usage:
    cd backend && python ../scripts/ab_compare.py
```

- Uses `eval_fixtures.QUICK_EVAL_PAIRS` (8 representative tests)
- Runs each test twice: once with `system=None` (old), once with `system=REEL_SYSTEM_PROMPT` (new)
- Compares: average composite score, per-metric averages, JSON validity rate
- Prints side-by-side scorecard
- **Gate:** new prompt must have higher avg composite AND ≥89% JSON validity

---

## Phase 4 — Best-of-N Gold Data Generation (Member B)

**Why:** Generate N candidates per input, keep only the best-scoring one. This produces high-quality training data entirely locally.

### `scripts/best_of_n_generate.py` — NEW script

```
Usage:
    cd backend && python ../scripts/best_of_n_generate.py --n 3
    cd backend && python ../scripts/best_of_n_generate.py --n 5 --min-score 0.7
```

- Extends existing `scripts/generate_training_data.py` pattern (same `load_sample_docs()`, `PREFERENCE_COMBOS` expanded to 8)
- For each doc x prefs combo: generate N=3 candidates via `generate_reels()`, score each with `score_reel()`, keep the best if score >= 0.6
- Vary temperature per attempt (0.3, 0.5, 0.7) to get diversity
- Output: `scripts/training_data_gold.jsonl` (same format as existing `training_data_raw.jsonl` plus `score` field)
- Also includes top-scoring reels from DB (those with `source_text IS NOT NULL AND score >= 0.6`)
- Target: 40-60 gold examples
- RAM safe: sequential generation, qwen2.5:1.5b uses ~1.2GB loaded

### 8 Preference Combos

```python
PREFERENCE_COMBOS = [
    {"learning_style": "visual",   "content_depth": "balanced", "use_case": "learning",  "flashcard_difficulty": "medium"},
    {"learning_style": "auditory", "content_depth": "balanced", "use_case": "exam",      "flashcard_difficulty": "medium"},
    {"learning_style": "reading",  "content_depth": "detailed", "use_case": "research",  "flashcard_difficulty": "hard"},
    {"learning_style": "mixed",    "content_depth": "brief",    "use_case": "work",      "flashcard_difficulty": "easy"},
    {"learning_style": "mixed",    "content_depth": "balanced", "use_case": "learning",  "flashcard_difficulty": "medium"},
    {"learning_style": "visual",   "content_depth": "brief",    "use_case": "exam",      "flashcard_difficulty": "easy"},
    {"learning_style": "reading",  "content_depth": "balanced", "use_case": "learning",  "flashcard_difficulty": "medium"},
    {"learning_style": "auditory", "content_depth": "detailed", "use_case": "research",  "flashcard_difficulty": "hard"},
]
```

---

## Phase 5 — Build ShareGPT Training Dataset (Member B)

### `scripts/convert_gold_to_sharegpt.py` — NEW script

Extends existing `scripts/convert_to_sharegpt.py`:

- Input: `scripts/training_data_gold.jsonl`
- Output: `scripts/verso_training_sharegpt_v2.json`
- System message includes `REEL_SYSTEM_PROMPT` content
- Gold examples with score >= 0.8 get duplicated (2x weight)
- Validates every example: output must parse as JSON with non-empty reels array

---

## Phase 6 — Fine-Tune on Colab (Member B)

### `scripts/verso_finetune.ipynb` — MODIFY

| Cell | Change |
|------|--------|
| Cell 3 | `MODEL_NAME = "unsloth/Qwen2.5-1.5B-Instruct"` (was 3B) |
| Cell 8 | Update system message to match `REEL_SYSTEM_PROMPT` |
| Cell 9 | Export path `"verso-qwen2.5-1.5b"` (was 3b) |
| Cell 10 | Update next-steps instructions for v2 model name |

GGUF output: ~900MB Q4_K_M (fits easily in 8GB RAM).

---

## Phase 7 — Deploy to Ollama (Member B)

### `scripts/Modelfile.v2` — NEW

```
FROM ./verso-qwen2.5-1.5b_gguf/verso-qwen2.5-1.5b.Q4_K_M.gguf

TEMPLATE """{{- if .Messages }}
... (same template as existing scripts/Modelfile)
{{ end }}{{ .Response }}{{ if .Response }}<|im_end|>{{ end }}"""

PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
PARAMETER temperature 0.3
PARAMETER num_ctx 2048
PARAMETER repeat_penalty 1.1
PARAMETER num_thread 4

SYSTEM """You are Verso, a learning content creator who teaches through short reels.
You are NOT a textbook. You explain like a friend.

CRITICAL RULES YOU MUST FOLLOW:
1. Use at least 3 contractions (don't, isn't, you're, it's, here's) in every narration.
2. Use "..." at least once and "—" at least once in every narration.
3. NEVER use: "is defined as", "refers to the process", "plays a crucial role",
   "it is important to note", "furthermore", "moreover".
4. Narration must be 40-60 words exactly.
5. Always output valid JSON with "reels" and "flashcards" arrays."""
```

**Deploy:**
```bash
cd scripts
ollama create verso-reel-v2 -f Modelfile.v2
```

**Swap model:** `export REEL_MODEL=verso-reel-v2` (config.py already reads from env)

---

## Phase 8 — A/B Model Eval (Member B)

### `scripts/ab_eval_models.py` — NEW script

```
Usage:
    cd backend && python ../scripts/ab_eval_models.py
```

- Tests both `qwen2.5:1.5b` (v1) and `verso-reel-v2` (v2) on `QUICK_EVAL_PAIRS`
- Patches `config.REEL_MODEL` between runs (evals all of model A first, then B, to minimize Ollama model swaps)
- Reports: JSON validity %, avg composite score, per-metric breakdown
- **Gate:** v2 JSON validity >= 89% AND v2 avg quality > v1 → ship v2

---

## Phase 9 — Orchestrator + Repeat Loop (Member B)

### `scripts/self_learning_loop.sh` — NEW

```bash
#!/bin/bash
set -e
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Verso Self-Learning Loop ==="

# Phase 1: Score existing reels
echo "[1/3] Scoring reels..."
python "$SCRIPTS_DIR/score_reels.py" --export "$SCRIPTS_DIR/scores_latest.jsonl"

# Phase 2: Generate best-of-N gold data
echo "[2/3] Generating gold training data (best-of-3)..."
python "$SCRIPTS_DIR/best_of_n_generate.py" --n 3 --min-score 0.65

# Phase 3: Convert to ShareGPT
echo "[3/3] Converting to ShareGPT format..."
python "$SCRIPTS_DIR/convert_gold_to_sharegpt.py"

echo ""
echo "=== Local phases complete ==="
echo "Gold data: $SCRIPTS_DIR/training_data_gold.jsonl"
echo "ShareGPT:  $SCRIPTS_DIR/verso_training_sharegpt_v2.json"
echo ""
echo "Next steps (manual):"
echo "  1. Upload verso_training_sharegpt_v2.json to Colab"
echo "  2. Run verso_finetune.ipynb"
echo "  3. Download GGUF to scripts/verso-qwen2.5-1.5b_gguf/"
echo "  4. ollama create verso-reel-v2 -f scripts/Modelfile.v2"
echo "  5. export REEL_MODEL=verso-reel-v2"
echo "  6. Run: python scripts/ab_eval_models.py"
```

**The repeat loop (post-deploy):**
```
verso-v2 outputs (now with source_text saved!)
    → score them with Phase 1 scorer
    → best-of-N on weak ones (Phase 4)
    → add best to training_data_v3.json
    → fine-tune → verso-v3
    → repeat
```

Each cycle: better data → better model → better data. Plateau after 2-3 cycles for 1.5B model.

---

## Files Summary

| File | Action | Phase | Member |
|------|--------|-------|--------|
| `backend/database.py` | MODIFY — add source_text migration | 0 | A |
| `backend/pipeline.py` | MODIFY — pass source_text to _save_reel | 0 | A |
| `backend/evals.py` | MODIFY — add metric_narration_quality + score_reel | 1 | A |
| `scripts/score_reels.py` | NEW — CLI to score all DB reels | 1 | A |
| `backend/prompts.py` | MODIFY — add REEL_SYSTEM_PROMPT, slim REEL_GENERATION_PROMPT | 2 | A |
| `backend/llm.py` | MODIFY — add system param to reel_llm_call + generate_reels | 2 | A |
| `scripts/ab_compare.py` | NEW — A/B prompt comparison | 3 | A |
| `scripts/best_of_n_generate.py` | NEW — gold data generator | 4 | B |
| `scripts/convert_gold_to_sharegpt.py` | NEW — ShareGPT v2 converter | 5 | B |
| `scripts/verso_finetune.ipynb` | MODIFY — target 1.5B model | 6 | B |
| `scripts/Modelfile.v2` | NEW — Ollama config for fine-tuned model | 7 | B |
| `scripts/ab_eval_models.py` | NEW — A/B model comparison | 8 | B |
| `scripts/self_learning_loop.sh` | NEW — orchestrator | 9 | B |

## RAM Budget

| Component | RAM |
|-----------|-----|
| Ollama + qwen2.5:1.5b | ~1.8 GB |
| Python backend | ~0.2 GB |
| Scoring/generation scripts | ~0.1 GB |
| OS | ~0.8 GB |
| **Peak total** | **~2.9 GB** (well under 5.5 GB ceiling) |

---

## Verification

### Member A verifies:
1. **Phase 0:** Upload a doc, check `SELECT source_text FROM reels ORDER BY id DESC LIMIT 1` returns non-null
2. **Phase 1:** Run `cd backend && python ../scripts/score_reels.py` — prints per-metric failure rates
3. **Phase 2-3:** Run `cd backend && python ../scripts/ab_compare.py` — new prompt scores higher

### Member B verifies:
4. **Phase 4-5:** Run best_of_n + convert — `verso_training_sharegpt_v2.json` has 40+ examples
5. **Phase 6-7:** After Colab training + deploy, `ollama run verso-reel-v2 "test"` responds
6. **Phase 8:** Run `cd backend && python ../scripts/ab_eval_models.py` — v2 beats v1 on composite score

### Integration test (after both merge):
7. Full loop: `cd backend && bash ../scripts/self_learning_loop.sh` completes without errors

---

## What Not to Do

- Don't train on examples without source text — a training pair without the input is useless
- Don't include low-scoring best-of-N outputs — the score >= 0.6 threshold exists for a reason
- Don't change the JSON schema between training and inference — if training data has `{"reels": [...], "flashcards": [...]}`, inference must expect the same
- Don't remove the few-shot example from inference unless the model has been retrained without it
- Don't skip Phase 0 — saving source text is a small change that makes every future improvement possible
