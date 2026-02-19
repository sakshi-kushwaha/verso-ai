"""
A/B compare: old prompt (no system prompt) vs new prompt (with REEL_SYSTEM_PROMPT).

Runs QUICK_EVAL_PAIRS through both variants and compares composite scores,
per-metric averages, and JSON validity rates.

Usage:
    cd backend && python ../scripts/ab_compare.py
    cd backend && python ../scripts/ab_compare.py --full   # all 40 tests instead of quick 8
"""

import json
import sys
import os
import time

backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
if not os.path.isdir(backend_dir):
    backend_dir = "/app"
sys.path.insert(0, backend_dir)

from eval_fixtures import TEST_DOCS, EVAL_COMBOS, QUICK_EVAL_PAIRS
from llm import generate_reels, reel_llm_call, REEL_MODEL
from evals import score_reel
from prompts import (
    REEL_GENERATION_PROMPT,
    REEL_SYSTEM_PROMPT,
    REEL_STYLE_INSTRUCTIONS,
    REEL_DEPTH_INSTRUCTIONS,
    REEL_USE_CASE_INSTRUCTIONS,
    DOC_TYPE_INSTRUCTIONS,
    FLASHCARD_DIFFICULTY_INSTRUCTIONS,
    REEL_FEW_SHOT,
)
from config import OLLAMA_HOST


def build_prompt(text, doc_type, prefs):
    """Build the user prompt (same logic as generate_reels but returns the string)."""
    return REEL_GENERATION_PROMPT.format(
        text=text[:3000],
        doc_type=doc_type,
        doc_type_instruction=DOC_TYPE_INSTRUCTIONS.get(doc_type, DOC_TYPE_INSTRUCTIONS["general"]),
        style_instruction=REEL_STYLE_INSTRUCTIONS.get(prefs.get("learning_style", "mixed"), REEL_STYLE_INSTRUCTIONS["mixed"]),
        depth_instruction=REEL_DEPTH_INSTRUCTIONS.get(prefs.get("content_depth", "balanced"), REEL_DEPTH_INSTRUCTIONS["balanced"]),
        use_case_instruction=REEL_USE_CASE_INSTRUCTIONS.get(prefs.get("use_case", "learning"), REEL_USE_CASE_INSTRUCTIONS["learning"]),
        difficulty_instruction=FLASHCARD_DIFFICULTY_INSTRUCTIONS.get(prefs.get("flashcard_difficulty", "medium"), FLASHCARD_DIFFICULTY_INSTRUCTIONS["medium"]),
        few_shot=REEL_FEW_SHOT,
    )


def generate_with_system(text, doc_type, prefs, system_prompt=None):
    """Generate reels using reel_llm_call with optional system prompt."""
    from llm import parse_llm_json
    prompt = build_prompt(text, doc_type, prefs)
    result = reel_llm_call(prompt, system=system_prompt)
    return parse_llm_json(result)


def run_variant(pairs, system_prompt, label):
    """Run all pairs with a given system prompt variant."""
    results = []
    for i, (doc, combo) in enumerate(pairs):
        print(f"  [{i+1}/{len(pairs)}] {doc['name']} + {combo['label']}...", end=" ", flush=True)
        try:
            output = generate_with_system(doc["text"], doc["doc_type"], combo, system_prompt)
            scored = score_reel(output, doc["text"], combo)
            scored["doc"] = doc["name"]
            scored["prefs"] = combo["label"]
            scored["json_ok"] = scored["metrics"]["json_valid"]["pass"]
            results.append(scored)
            print(f"score={scored['composite_score']:.3f}")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "composite_score": 0.0,
                "doc": doc["name"],
                "prefs": combo["label"],
                "json_ok": False,
                "metrics": {},
            })
    return results


def print_comparison(results_a, results_b):
    """Print side-by-side comparison of two variants."""
    def avg(lst, key):
        vals = [x[key] for x in lst if key in x]
        return sum(vals) / len(vals) if vals else 0.0

    def json_rate(lst):
        ok = sum(1 for x in lst if x.get("json_ok", False))
        return ok / len(lst) * 100 if lst else 0.0

    print("\n" + "=" * 65)
    print(f"{'METRIC':<30s}  {'OLD (no system)':>15s}  {'NEW (system)':>15s}")
    print("=" * 65)

    # Composite
    avg_a = avg(results_a, "composite_score")
    avg_b = avg(results_b, "composite_score")
    delta = avg_b - avg_a
    arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
    print(f"{'Composite score':<30s}  {avg_a:>14.3f}  {avg_b:>14.3f}  {arrow} {abs(delta):.3f}")

    # JSON validity
    jr_a = json_rate(results_a)
    jr_b = json_rate(results_b)
    print(f"{'JSON validity':<30s}  {jr_a:>13.0f}%  {jr_b:>13.0f}%")

    # Per-metric averages
    metric_names = ["json_valid", "schema_complete", "depth_match", "style_match",
                    "content_quality", "flashcard_quality", "narration_quality"]
    print("-" * 65)
    for metric in metric_names:
        scores_a = [r["metrics"].get(metric, {}).get("score", 0) for r in results_a if r.get("metrics")]
        scores_b = [r["metrics"].get(metric, {}).get("score", 0) for r in results_b if r.get("metrics")]
        ma = sum(scores_a) / len(scores_a) if scores_a else 0
        mb = sum(scores_b) / len(scores_b) if scores_b else 0
        d = mb - ma
        arrow = "↑" if d > 0.01 else "↓" if d < -0.01 else "="
        print(f"  {metric:<28s}  {ma:>14.3f}  {mb:>14.3f}  {arrow}")

    print("=" * 65)

    # Gate check
    print("\nGATE CHECK:")
    gate_json = jr_b >= 89
    gate_quality = avg_b > avg_a
    print(f"  JSON validity >= 89%:     {'PASS' if gate_json else 'FAIL'} ({jr_b:.0f}%)")
    print(f"  Quality improvement:      {'PASS' if gate_quality else 'FAIL'} ({avg_a:.3f} → {avg_b:.3f})")
    if gate_json and gate_quality:
        print("\n  ✓ SHIP the new prompt!")
    else:
        print("\n  ✗ Keep the old prompt — new version didn't pass the gate.")


def main():
    full = "--full" in sys.argv

    print(f"A/B Prompt Comparison — Model: {REEL_MODEL}")
    print(f"Ollama: {OLLAMA_HOST}")
    print()

    # Build test pairs
    if full:
        pairs = [(doc, combo) for doc in TEST_DOCS for combo in EVAL_COMBOS]
        print(f"Running FULL eval: {len(pairs)} tests\n")
    else:
        pairs = []
        for doc_name, combo_label in QUICK_EVAL_PAIRS:
            doc = next(d for d in TEST_DOCS if d["name"] == doc_name)
            combo = next(c for c in EVAL_COMBOS if c["label"] == combo_label)
            pairs.append((doc, combo))
        print(f"Running QUICK eval: {len(pairs)} tests\n")

    # Variant A: no system prompt (old behavior)
    print("── Variant A: NO system prompt (baseline) ──")
    start_a = time.time()
    results_a = run_variant(pairs, system_prompt=None, label="old")
    time_a = time.time() - start_a

    # Variant B: with system prompt (new behavior)
    print(f"\n── Variant B: WITH system prompt (new) ──")
    start_b = time.time()
    results_b = run_variant(pairs, system_prompt=REEL_SYSTEM_PROMPT, label="new")
    time_b = time.time() - start_b

    # Print comparison
    print_comparison(results_a, results_b)
    print(f"\nTime: A={time_a:.0f}s  B={time_b:.0f}s")

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "ab_compare_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "model": REEL_MODEL,
            "variant_a": [{"composite": r["composite_score"], "doc": r["doc"], "prefs": r["prefs"]} for r in results_a],
            "variant_b": [{"composite": r["composite_score"], "doc": r["doc"], "prefs": r["prefs"]} for r in results_b],
        }, f, indent=2)
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
