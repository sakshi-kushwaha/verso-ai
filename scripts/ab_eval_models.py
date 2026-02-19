"""
A/B Model Evaluation — Compare base model vs fine-tuned model.

Tests both models on QUICK_EVAL_PAIRS and compares composite scores.
Patches config.REEL_MODEL between runs to minimize Ollama model swaps.

Usage:
    cd backend && python ../scripts/ab_eval_models.py
    cd backend && python ../scripts/ab_eval_models.py --model-a qwen2.5:1.5b --model-b verso-reel-v2
"""

import json
import sys
import os
import time
import argparse

backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
if not os.path.isdir(backend_dir):
    backend_dir = "/app"
sys.path.insert(0, backend_dir)

import config
from llm import generate_reels
from evals import score_reel
from eval_fixtures import QUICK_EVAL_PAIRS, TEST_DOCS
from prompts import REEL_SYSTEM_PROMPT

SCRIPT_DIR = os.path.dirname(__file__)
RESULTS_FILE = os.path.join(SCRIPT_DIR, "ab_model_results.json")


def run_eval(model_name: str, label: str) -> list:
    """Run all QUICK_EVAL_PAIRS with a specific model, return per-test results."""
    # Patch the model at runtime
    config.REEL_MODEL = model_name
    # Also need to reimport to pick up config change in llm module
    import llm
    llm.REEL_MODEL = model_name

    results = []
    total = len(QUICK_EVAL_PAIRS)

    print(f"\n── {label}: {model_name} ──")
    for i, (doc_key, prefs) in enumerate(QUICK_EVAL_PAIRS):
        tag = f"{doc_key} + {prefs['learning_style']}+{prefs['content_depth']}+{prefs['use_case']}"
        print(f"  [{i+1}/{total}] {tag}...", end=" ", flush=True)

        text = TEST_DOCS[doc_key][:3000]
        try:
            output = generate_reels(text, "general", prefs)
            score_result = score_reel(output, text, prefs)
            score = score_result["composite_score"]
            metrics = {k: v["score"] for k, v in score_result["metrics"].items()}
            json_ok = metrics.get("json_valid", 0) == 1.0
            print(f"score={score:.3f}")
        except Exception as e:
            print(f"ERROR: {e}")
            score = 0.0
            metrics = {}
            json_ok = False

        results.append({
            "doc": doc_key,
            "prefs": prefs,
            "score": score,
            "metrics": metrics,
            "json_ok": json_ok,
        })

    return results


def print_comparison(results_a: list, results_b: list, name_a: str, name_b: str):
    """Print side-by-side comparison table."""
    # Aggregate
    avg_a = sum(r["score"] for r in results_a) / len(results_a) if results_a else 0
    avg_b = sum(r["score"] for r in results_b) / len(results_b) if results_b else 0
    json_a = sum(1 for r in results_a if r["json_ok"]) / len(results_a) * 100 if results_a else 0
    json_b = sum(1 for r in results_b if r["json_ok"]) / len(results_b) * 100 if results_b else 0

    # Per-metric averages
    all_metrics = set()
    for r in results_a + results_b:
        all_metrics.update(r.get("metrics", {}).keys())

    print(f"\n{'='*65}")
    print(f"{'METRIC':<30} {name_a:>15} {name_b:>15}")
    print(f"{'='*65}")
    diff = avg_b - avg_a
    arrow = "↑" if diff > 0.005 else "↓" if diff < -0.005 else "="
    print(f"{'Composite score':<30} {avg_a:>14.3f}  {avg_b:>14.3f}  {arrow} {diff:+.3f}")
    print(f"{'JSON validity':<30} {json_a:>13.0f}%  {json_b:>13.0f}%")
    print(f"{'-'*65}")

    for metric in sorted(all_metrics):
        vals_a = [r["metrics"].get(metric, 0) for r in results_a]
        vals_b = [r["metrics"].get(metric, 0) for r in results_b]
        ma = sum(vals_a) / len(vals_a) if vals_a else 0
        mb = sum(vals_b) / len(vals_b) if vals_b else 0
        arrow = "↑" if mb - ma > 0.005 else "↓" if mb - ma < -0.005 else "="
        print(f"  {metric:<28} {ma:>14.3f}  {mb:>14.3f}  {arrow}")

    print(f"{'='*65}")

    # Gate check
    print(f"\nGATE CHECK:")
    json_pass = json_b >= 89
    quality_pass = avg_b > avg_a
    print(f"  JSON validity >= 89%:     {'PASS' if json_pass else 'FAIL'} ({json_b:.0f}%)")
    print(f"  Quality improvement:      {'PASS' if quality_pass else 'FAIL'} ({avg_a:.3f} → {avg_b:.3f})")

    if json_pass and quality_pass:
        print(f"\n  ✓ SHIP {name_b}! Fine-tuned model outperforms baseline.")
    else:
        print(f"\n  ✗ Keep {name_a} — fine-tuned model didn't pass the gate.")

    return {"json_pass": json_pass, "quality_pass": quality_pass}


def main():
    parser = argparse.ArgumentParser(description="A/B model evaluation")
    parser.add_argument("--model-a", type=str, default="qwen2.5:1.5b", help="Base model (default: qwen2.5:1.5b)")
    parser.add_argument("--model-b", type=str, default="verso-reel-v2", help="Fine-tuned model (default: verso-reel-v2)")
    args = parser.parse_args()

    print(f"A/B Model Evaluation")
    print(f"  Model A (base):      {args.model_a}")
    print(f"  Model B (fine-tuned): {args.model_b}")
    print(f"  Tests: {len(QUICK_EVAL_PAIRS)}")

    # Run Model A first (all tests), then Model B (minimizes Ollama model swaps)
    t0 = time.time()
    results_a = run_eval(args.model_a, "Model A (base)")
    t1 = time.time()
    results_b = run_eval(args.model_b, "Model B (fine-tuned)")
    t2 = time.time()

    gate = print_comparison(results_a, results_b, args.model_a, args.model_b)

    print(f"\nTime: A={t1-t0:.0f}s  B={t2-t1:.0f}s")

    # Save results
    output = {
        "model_a": args.model_a,
        "model_b": args.model_b,
        "results_a": results_a,
        "results_b": results_b,
        "gate": gate,
    }
    with open(RESULTS_FILE, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Results saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
