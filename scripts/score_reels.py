"""
Score all reels in the database using the narration quality scorer.

Reports per-metric failure rates and identifies the most-violated rules
so you know which rules to promote into the system prompt.

Usage:
    cd backend && python ../scripts/score_reels.py
    cd backend && python ../scripts/score_reels.py --export scores.jsonl
"""

import json
import sys
import os

backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
if not os.path.isdir(backend_dir):
    backend_dir = "/app"
sys.path.insert(0, backend_dir)

from database import get_db
from evals import score_reel


def main():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, upload_id, title, summary, narration, category, keywords, source_text "
            "FROM reels"
        ).fetchall()
    except Exception:
        print("No reels table in DB yet. Run the pipeline on a document first.")
        conn.close()
        return
    conn.close()

    if not rows:
        print("No reels in DB. Run the pipeline on a document first.")
        return

    print(f"Scoring {len(rows)} reels...\n")

    scores = []
    violation_counts = {}

    for row in rows:
        reel_dict = {
            "reels": [{
                "title": row["title"] or "",
                "summary": row["summary"] or "",
                "narration": row["narration"] or "",
                "category": row["category"] or "",
                "keywords": row["keywords"] or "",
            }],
            "flashcards": [],  # can't recover flashcards from reels table alone
        }
        source_text = row["source_text"] or ""
        result = score_reel(reel_dict, source_text)
        result["reel_id"] = row["id"]
        result["upload_id"] = row["upload_id"]
        result["title"] = row["title"] or ""
        scores.append(result)

        for metric, data in result["metrics"].items():
            if not data.get("pass", False):
                violation_counts[metric] = violation_counts.get(metric, 0) + 1

    # Sort by composite score
    scores.sort(key=lambda x: x["composite_score"], reverse=True)

    # Report averages
    avg_composite = sum(s["composite_score"] for s in scores) / len(scores)
    print(f"Average composite score: {avg_composite:.3f}")

    # Per-metric failure rates
    print("\nPer-metric failure rates (most violated first):")
    for metric, count in sorted(violation_counts.items(), key=lambda x: -x[1]):
        pct = count / len(scores) * 100
        print(f"  {metric:<22s}  {count:3d}/{len(scores)}  ({pct:5.1f}% fail)")

    # Per-metric average scores
    metric_names = list(scores[0]["metrics"].keys())
    print("\nPer-metric average scores:")
    for metric in metric_names:
        avg = sum(s["metrics"][metric]["score"] for s in scores) / len(scores)
        print(f"  {metric:<22s}  {avg:.3f}")

    # Top 25% and bottom 25%
    quarter = max(1, len(scores) // 4)

    print(f"\n── TOP {quarter} reels (training candidates) ──")
    for s in scores[:quarter]:
        print(f"  Reel {s['reel_id']:4d}: {s['composite_score']:.3f} — {s['title'][:50]}")

    print(f"\n── BOTTOM {quarter} reels (need fixing) ──")
    for s in scores[-quarter:]:
        print(f"  Reel {s['reel_id']:4d}: {s['composite_score']:.3f} — {s['title'][:50]}")

    # Export
    if "--export" in sys.argv:
        idx = sys.argv.index("--export")
        path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "scores.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for s in scores:
                f.write(json.dumps(s, ensure_ascii=False, default=str) + "\n")
        print(f"\nExported to {path}")


if __name__ == "__main__":
    main()
