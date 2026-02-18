# Verso - Task Breakdown

**Timeline:** 4 Days (Feb 16-19) | **Demo:** Feb 23
**Target:** EC2 `c6i.xlarge` (4 vCPU, 8 GB RAM, 20 GB gp3 EBS)
**Team:** 3 Engineers — Sanika, Sakshi, Esha

---

## Project Summary

Verso is an AI-powered learning platform that transforms uploaded documents (PDF/DOCX) into short, swipeable educational reels with TTS narration, flashcards, and RAG-based chat Q&A.

**Tech stack:** FastAPI backend, React + Vite frontend, SQLite, Qwen 2.5 3B via Ollama, nomic-embed-text for RAG embeddings, Piper/espeak TTS, Pixabay stock videos, ffmpeg video composition. All running on a single 8 GB EC2 instance.

**Days 1-3 (complete):** Full end-to-end pipeline delivered — document upload/parsing, reel generation with personalization (learning style, depth, use case), video reels with stock footage + category-specific background music, swipeable feed with flashcard interleaving, auth + onboarding, bookmarks, progress tracking, download, My Collections, chat Q&A with RAG, and a LoRA fine-tuned model. Eval system at 97.9% structural pass rate across 5 doc types (textbook, research, business, fiction, technical).

**Current focus:** Reel content quality. The pipeline is structurally solid but reels feel generic — summaries read like textbook excerpts, narration sounds robotic, and there's no engaging hook. Day 4 targets this gap through benchmark generation, model exploration, and self-learning data collection.

---

## Day 4 — Reel Quality & Model Exploration (Feb 19)

**Goal:** Generate gold-standard benchmark reels, validate platform reel generation end-to-end, set up a self-learning pipeline for iterative model improvement, and evaluate Qwen 3 4B as a potential upgrade.

### Sanika — Benchmark Reel Generation (10-15 Gold-Standard Reels)

Generate high-quality reference reels using a stronger model to establish the quality bar the team aims for.

- [ ] Pick 2-3 documents already tested in the pipeline (varied doc types — textbook, research, business)
- [ ] Generate 10-15 reels using a top-tier model (Claude/GPT-4), following the exact pipeline JSON schema:
  ```json
  {"reels":[{"title":"...","summary":"...","narration":"...","category":"...","keywords":"..."}],
   "flashcards":[{"question":"...?","answer":"..."}]}
  ```
- [ ] Focus on quality: strong hooks (question/surprising fact/bold claim), conversational narration that sounds natural when read aloud, varied sentence lengths and pacing
- [ ] Save all benchmark reels in a shared file for side-by-side comparison with current Qwen output
- [ ] Document the patterns that make benchmark reels better (hooks, tone, narrative arc, specificity)

### Sakshi — Platform Reel Generation & Self-Learning Pipeline

Validate real reel generation on the live platform and design the self-learning data flow for future fine-tuning rounds.

- [ ] Upload 3-5 new documents through the live platform — full end-to-end flow (upload → parse → generate → video compose)
- [ ] Verify everything works: reels in feed with stock videos, TTS narration, flashcard interleaving, bookmarks, chat Q&A
- [ ] Log any pipeline issues during real generation (timeouts, malformed JSON, missing videos, edge cases)
- [ ] Design self-learning data collection: capture high-quality outputs (benchmark reels + best Qwen outputs) as training data
- [ ] Set up a flow to save curated reels in ShareGPT/training format (building on existing `scripts/verso_training_sharegpt.json` and `scripts/convert_to_sharegpt.py`)
- [ ] Document the self-learning strategy: how curated outputs feed back into the LoRA fine-tuning pipeline (`scripts/verso_finetune.ipynb`) for iterative improvement

### Esha — Model Testing & Eval (Qwen 3 4B)

Evaluate Qwen 3 4B as a potential model upgrade — quality, RAM, speed tradeoffs.

- [ ] Pull and set up Qwen 3 4B on Ollama
- [ ] Check RAM usage — must stay under 5.5 GB peak during generation (8 GB EC2 budget)
- [ ] Run the existing eval suite (`backend/evals.py`) against Qwen 3 4B — compare structural metrics vs Qwen 2.5 3B baseline (97.9%)
- [ ] Generate reels for the same 2-3 test documents Sanika is benchmarking (directly comparable results)
- [ ] Manual quality review: score 3-5 reels on hook quality, narration tone, summary depth (1-5 scale) vs current output
- [ ] Measure inference speed: time per reel batch with Qwen 3 4B vs 2.5 3B (600s timeout budget)
- [ ] Document findings: is Qwen 3 4B a viable upgrade? Quality delta, RAM impact, speed tradeoff

---

## Success Criteria (Day 4)

- [ ] 10-15 benchmark reels generated and shared for team review (Sanika)
- [ ] 3-5 documents processed end-to-end on the live platform without issues (Sakshi)
- [ ] Self-learning data collection approach documented and prototyped (Sakshi)
- [ ] Qwen 3 4B eval results documented with quality comparison vs 2.5 3B (Esha)
- [ ] RAM usage confirmed within 8 GB budget for any model changes (Esha)
