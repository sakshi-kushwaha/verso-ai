#!/usr/bin/env bash
#
# Verso Self-Learning Loop — Orchestrator
#
# Runs the full self-learning pipeline:
#   1. Score existing reels (identify weaknesses)
#   2. Generate best-of-N gold training data
#   3. Convert to ShareGPT format for fine-tuning
#   4. (Manual) Fine-tune on Colab, download GGUF
#   5. (Manual) Deploy to Ollama
#   6. (Manual) A/B eval new model vs old
#
# Usage:
#   bash scripts/self_learning_loop.sh           # run from project root
#   bash scripts/self_learning_loop.sh --n 5     # 5 candidates per input
#
# Prerequisites:
#   - Ollama running with qwen2.5:3b loaded
#   - Sample docs in scripts/sample_docs/
#   - Backend dependencies installed
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

# Default args
N="${1:-3}"
MIN_SCORE="${2:-0.6}"

echo "============================================="
echo " Verso Self-Learning Loop"
echo "============================================="
echo " Working dir: $BACKEND_DIR"
echo " Candidates per input: $N"
echo " Min score threshold: $MIN_SCORE"
echo "============================================="
echo ""

# --------------------------------------------------
# Phase 1: Score existing reels
# --------------------------------------------------
echo "── Phase 1: Scoring existing reels ──"
cd "$BACKEND_DIR"
python3 "$SCRIPT_DIR/score_reels.py" --export "$SCRIPT_DIR/scores_latest.jsonl" || true
echo ""

# --------------------------------------------------
# Phase 2: Generate best-of-N gold training data
# --------------------------------------------------
echo "── Phase 2: Generating best-of-N gold data ──"
cd "$BACKEND_DIR"
python3 "$SCRIPT_DIR/best_of_n_generate.py" --n "$N" --min-score "$MIN_SCORE"
echo ""

# --------------------------------------------------
# Phase 3: Convert to ShareGPT format
# --------------------------------------------------
echo "── Phase 3: Converting to ShareGPT v2 format ──"
python3 "$SCRIPT_DIR/convert_gold_to_sharegpt.py"
echo ""

# --------------------------------------------------
# Summary
# --------------------------------------------------
echo "============================================="
echo " Automated phases complete!"
echo "============================================="
echo ""
echo " Generated files:"
echo "   - $SCRIPT_DIR/scores_latest.jsonl         (reel scores)"
echo "   - $SCRIPT_DIR/training_data_gold.jsonl     (gold training data)"
echo "   - $SCRIPT_DIR/verso_training_sharegpt_v2.json (ShareGPT for Colab)"
echo ""
echo " Manual steps remaining:"
echo "   1. Upload verso_training_sharegpt_v2.json to Google Colab"
echo "   2. Run scripts/verso_finetune.ipynb (fine-tune on T4 GPU)"
echo "   3. Download the GGUF file from Colab"
echo "   4. Place it in scripts/verso-qwen2.5-3b_gguf/"
echo "   5. Deploy: ollama create verso-reel-v2 -f scripts/Modelfile.v2"
echo "   6. Evaluate: cd backend && python ../scripts/ab_eval_models.py"
echo ""
echo " If the A/B eval passes the gate, update your config:"
echo "   export REEL_MODEL=verso-reel-v2"
echo "============================================="
