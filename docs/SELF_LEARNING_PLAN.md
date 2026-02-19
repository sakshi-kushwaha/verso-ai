# Self-Learning Pipeline for Reel Generation

The reel generation model (qwen2.5:1.5b) follows prompt rules inconsistently — contractions, pauses, conversational starters, and word count targets are often ignored. There's no feedback loop: reels are generated once and never evaluated. This plan adds a closed-loop self-learning pipeline: **score reels → identify weaknesses → fix prompts → generate gold training data → fine-tune → deploy → repeat**.

The codebase already has evaluation infrastructure (`evals.py`, `eval_fixtures.py`), training data generation (`scripts/generate_training_data.py`), ShareGPT conversion (`scripts/convert_to_sharegpt.py`), and a Colab fine-tuning notebook (`scripts/verso_finetune.ipynb`). This plan extends and connects these existing pieces.

**PR:** [#132 — Self-learning pipeline](https://github.com/sakshi-kushwaha/verso-ai/pull/132)

---

## Implementation Status

### Member 1 (Sakshi) — ALL CODE COMPLETE

Sakshi implemented **all 9 phases** (both Member A and Member B tasks). All code is written, tested, committed, and pushed to the `self-learning-backend` branch.

| Phase | Task | Status | Files |
|-------|------|--------|-------|
| 0 | Save source_text | DONE | `backend/database.py`, `backend/pipeline.py` |
| 1 | Narration scorer | DONE | `backend/evals.py`, `scripts/score_reels.py` |
| 2 | System prompt + LLM wiring | DONE | `backend/prompts.py`, `backend/llm.py` |
| 3 | A/B prompt compare | DONE | `scripts/ab_compare.py` |
| 4 | Best-of-N generator | DONE | `scripts/best_of_n_generate.py` |
| 5 | ShareGPT v2 converter | DONE | `scripts/convert_gold_to_sharegpt.py` |
| 6 | Update Colab notebook | DONE | `scripts/verso_finetune.ipynb` |
| 7 | Modelfile v2 | DONE | `scripts/Modelfile.v2` |
| 8 | A/B model eval | DONE | `scripts/ab_eval_models.py` |
| 9 | Orchestrator | DONE | `scripts/self_learning_loop.sh` |

#### Test Results (Phases 0-3)

| Test | Result |
|------|--------|
| Scorer sanity check | PASS — good reel: 1.0, bad textbook reel: 0.14 narration |
| A/B prompt comparison | PASS — new prompt 0.950 vs baseline 0.887 |
| Score existing DB reels | PASS — 9 reels scored, avg 0.754 |
| DB source_text check | PASS — column exists, new uploads will populate it |

#### A/B Prompt Results

| Metric | Old (no system prompt) | New (with system prompt) |
|--------|----------------------|------------------------|
| Composite | 0.887 | **0.950** |
| style_match | 0.750 | **1.000** |
| flashcard_quality | 0.844 | **0.969** |
| narration_quality | 0.753 | **0.836** |
| JSON validity | 100% | 100% |

---

### Member 2 (Esha) — MANUAL STEPS REMAINING

All scripts and infrastructure are ready. Esha needs to **run the pipeline** and perform the manual fine-tuning steps that require Google Colab and human judgment.

---

## Esha's Step-by-Step Guide

### Prerequisites

1. Docker running with `docker compose up -d`
2. Ollama has `qwen2.5:1.5b` pulled: `docker compose exec ollama ollama pull qwen2.5:1.5b`
3. At least 5-10 sample text documents for training data generation

### Step 1: Add Sample Documents

Create representative text files for training. These should cover different document types.

```bash
mkdir -p scripts/sample_docs/

# Add .txt files — one per document. Examples:
# - A biology textbook chapter
# - A research paper abstract + findings
# - A business quarterly report
# - A short fiction excerpt
# - API documentation
```

**Research needed:** Pick 5-10 diverse documents that represent what users actually upload. The more diverse, the better the training data. Each file should be 500-3000 words.

### Step 2: Run the Automated Pipeline

```bash
# From project root — runs Phases 1, 4, 5 automatically
bash scripts/self_learning_loop.sh
```

This will:
1. Score existing reels in the DB (identifies weaknesses)
2. Generate best-of-3 candidates per doc x prefs combo, keep the best
3. Convert gold examples to ShareGPT v2 format

**Output files:**
- `scripts/scores_latest.jsonl` — current reel quality scores
- `scripts/training_data_gold.jsonl` — gold training examples
- `scripts/verso_training_sharegpt_v2.json` — ready for Colab upload

**What to check:** The script prints how many gold examples were generated. Target is 40-60. If you get fewer than 20, add more sample docs and re-run.

### Step 3: Fine-Tune on Google Colab (Manual)

1. Open `scripts/verso_finetune.ipynb` in [Google Colab](https://colab.research.google.com/)
2. Set runtime to **T4 GPU** (Runtime → Change runtime type → T4)
3. Upload `scripts/verso_training_sharegpt_v2.json` when prompted (Cell 2)
4. Run all cells sequentially (Cell 1 through Cell 9)
5. Cell 9 will export and auto-download the GGUF file

**Research needed:**
- Training takes ~15-20 min on free T4
- Watch the training loss in Cell 7 — it should decrease steadily
- Cell 8 runs a test generation — verify the output looks like valid JSON with reels/flashcards
- If training loss plateaus above 1.5, consider: more training data, or adjusting learning rate in Cell 6

**Troubleshooting:**
- OOM crash → Restart runtime, re-run from Cell 1
- Slow/disconnects → Use "Prevent disconnection" browser extension

### Step 4: Deploy Fine-Tuned Model to EC2

The project has CI/CD via GitHub Actions (`.github/workflows/deploy.yml`). On push to `main`, it auto-deploys to EC2. But the fine-tuned GGUF model needs to be deployed separately since it's too large for git.

**Option A: SCP the GGUF directly to EC2**
```bash
# From your local machine
scp ~/Downloads/verso-qwen2.5-1.5b.Q4_K_M.gguf <EC2_USER>@<EC2_HOST>:/root/verso-ai/scripts/verso-qwen2.5-1.5b_gguf/

# SSH into EC2 and create the Ollama model
ssh <EC2_USER>@<EC2_HOST>
cd /root/verso-ai/scripts
mkdir -p verso-qwen2.5-1.5b_gguf
ollama create verso-reel-v2 -f Modelfile.v2
ollama run verso-reel-v2 "Say hello"  # verify it responds
```

**Option B: Test locally first, then deploy**
```bash
# Local test
mkdir -p scripts/verso-qwen2.5-1.5b_gguf/
mv ~/Downloads/verso-qwen2.5-1.5b.Q4_K_M.gguf scripts/verso-qwen2.5-1.5b_gguf/
cd scripts && ollama create verso-reel-v2 -f Modelfile.v2
ollama run verso-reel-v2 "Say hello"
# If good, SCP to EC2 (Option A)
```

**What to check:** The model should respond. If `ollama create` fails, check the GGUF file path matches what's in `Modelfile.v2`.

### Step 5: A/B Evaluate Models

Run on EC2 (where production reels are generated):

```bash
ssh <EC2_USER>@<EC2_HOST>
cd /root/verso-ai/backend
source venv/bin/activate
python ../scripts/ab_eval_models.py
```

Or locally via Docker:
```bash
docker compose exec backend python /scripts/ab_eval_models.py
```

This compares `qwen2.5:1.5b` (base) vs `verso-reel-v2` (fine-tuned) on 8 test cases.

**Gate criteria:**
- JSON validity >= 89%
- Fine-tuned model composite score > base model composite score

**If the gate PASSES — switch production to v2:**

On EC2, update the systemd override or the uvicorn start command to set the env var:
```bash
ssh <EC2_USER>@<EC2_HOST>
# Add to the server startup (update ec2-setup.sh or the nohup command in deploy.yml)
export REEL_MODEL=verso-reel-v2
# Restart the server
pkill -f "uvicorn main:app"
cd /root/verso-ai/backend && source venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /root/verso-ai/server.log 2>&1 &
```

To make this permanent across CI/CD deploys, update `ec2-setup.sh` to add:
```bash
# After Ollama model pulls, also create fine-tuned model if GGUF exists
if [ -f "${APP_DIR}/scripts/verso-qwen2.5-1.5b_gguf/verso-qwen2.5-1.5b.Q4_K_M.gguf" ]; then
    ollama create verso-reel-v2 -f "${APP_DIR}/scripts/Modelfile.v2"
fi
```

And update the restart step in `deploy.yml` to include the env var:
```yaml
REEL_MODEL=verso-reel-v2 nohup uvicorn main:app --host 0.0.0.0 --port 8000 ...
```

**If the gate FAILS:**
- Check which metrics dropped — the script prints per-metric breakdown
- Likely causes: not enough training data, or training data quality too low
- Fix: add more sample docs, re-run Step 2, increase `--n` to 5 for more candidates
- Re-train and re-evaluate

### Step 6: Repeat the Loop (Future Cycles)

After deploying v2, new uploads will generate reels with the improved model **and** save `source_text`. This means:

```
v2 generates better reels (with source_text saved)
    → Score them: python scripts/score_reels.py  (on EC2)
    → Generate best-of-N from weak areas
    → Fine-tune → verso-reel-v3
    → A/B eval → deploy if better
    → Repeat
```

Each cycle improves the model. Expect diminishing returns after 2-3 cycles for 1.5B.

### CI/CD Integration Notes

The existing CI/CD pipeline (`.github/workflows/deploy.yml`) handles:
- Build frontend → SCP static files to EC2
- `git pull` + `bash ec2-setup.sh --deploy` on EC2
- Restart uvicorn

**What CI/CD does NOT handle (manual steps for Esha):**
- GGUF model files (too large for git — SCP directly to EC2)
- `ollama create` for the fine-tuned model (run once on EC2)
- Setting `REEL_MODEL` env var (update deploy.yml or ec2-setup.sh)
- Running the self-learning loop (run on EC2 where Ollama + models are available)

---

## Esha's Research Checklist

These are things Esha should investigate/decide:

- [ ] **Sample documents:** Curate 5-10 diverse .txt files covering biology, business, tech, history, fiction, etc. Quality of training data directly impacts model quality.
- [ ] **Gold data threshold:** Default min-score is 0.6. After reviewing `training_data_gold.jsonl`, decide if this should be raised (stricter = fewer but better examples) or lowered (more examples but noisier).
- [ ] **Training hyperparameters:** The notebook uses 3 epochs, lr=2e-4, batch_size=2. If the model overfits (test output looks memorized), reduce epochs to 2. If underfits (output still bad), increase to 5.
- [ ] **GGUF quantization:** Default is Q4_K_M (~900MB). If quality is borderline, try Q5_K_M (~1.1GB) for slightly better quality at the cost of more RAM.
- [ ] **CI/CD integration:** After A/B eval passes, decide how to persist `REEL_MODEL=verso-reel-v2` across deploys. Options: (a) update the `nohup` command in `deploy.yml` to include the env var, (b) add it to `ec2-setup.sh`, or (c) create a `/root/.env` file sourced at startup.
- [ ] **EC2 RAM check:** On the 8GB EC2 instance, verify peak RAM stays under 5.5GB ceiling after model swap. SSH in and run `free -h` during a test upload. The fine-tuned 1.5B Q4_K_M model should use roughly the same RAM as the base qwen2.5:1.5b.
- [ ] **GGUF storage:** The GGUF file (~900MB) is too large for git. Decide on a permanent storage strategy: (a) keep on EC2 only, (b) upload to a private S3 bucket and pull during setup, or (c) store in Google Drive alongside the Colab notebook.

---

## Files Summary

| File | Action | Phase | Status |
|------|--------|-------|--------|
| `backend/database.py` | MODIFY — add source_text migration | 0 | DONE |
| `backend/pipeline.py` | MODIFY — pass source_text to _save_reel | 0 | DONE |
| `backend/evals.py` | MODIFY — add metric_narration_quality + score_reel | 1 | DONE |
| `scripts/score_reels.py` | NEW — CLI to score all DB reels | 1 | DONE |
| `backend/prompts.py` | MODIFY — add REEL_SYSTEM_PROMPT + restored narration rules | 2 | DONE |
| `backend/llm.py` | MODIFY — add system param to reel_llm_call + generate_reels | 2 | DONE |
| `scripts/ab_compare.py` | NEW — A/B prompt comparison | 3 | DONE |
| `scripts/best_of_n_generate.py` | NEW — gold data generator | 4 | DONE |
| `scripts/convert_gold_to_sharegpt.py` | NEW — ShareGPT v2 converter | 5 | DONE |
| `scripts/verso_finetune.ipynb` | MODIFY — target 1.5B model | 6 | DONE |
| `scripts/Modelfile.v2` | NEW — Ollama config for fine-tuned model | 7 | DONE |
| `scripts/ab_eval_models.py` | NEW — A/B model comparison | 8 | DONE |
| `scripts/self_learning_loop.sh` | NEW — orchestrator | 9 | DONE |

## RAM Budget

| Component | RAM |
|-----------|-----|
| Ollama + qwen2.5:1.5b | ~1.8 GB |
| Python backend | ~0.2 GB |
| Scoring/generation scripts | ~0.1 GB |
| OS | ~0.8 GB |
| **Peak total** | **~2.9 GB** (well under 5.5 GB ceiling) |

---

## What Not to Do

- Don't train on examples without source text — a training pair without the input is useless
- Don't include low-scoring best-of-N outputs — the score >= 0.6 threshold exists for a reason
- Don't change the JSON schema between training and inference — if training data has `{"reels": [...], "flashcards": [...]}`, inference must expect the same
- Don't remove the few-shot example from inference unless the model has been retrained without it
- Don't skip the A/B eval — always compare before deploying a new model version
- Don't deploy a model that fails the gate — if JSON validity drops below 89%, the model will break the pipeline
