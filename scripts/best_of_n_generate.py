"""
Best-of-N Gold Training Data Generator for Verso self-learning pipeline.

Generates N candidates per input text + preference combo, scores each
with score_reel(), and keeps only the highest-scoring one (if above threshold).

Usage:
    cd backend && python ../scripts/best_of_n_generate.py
    cd backend && python ../scripts/best_of_n_generate.py --n 5 --min-score 0.7

Input:  scripts/sample_docs/*.txt  (same as generate_training_data.py)
Output: scripts/training_data_gold.jsonl
"""

import json
import sys
import os
import argparse
import sqlite3

# Add backend to path so we can import project modules
backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
if not os.path.isdir(backend_dir):
    backend_dir = "/app"  # inside Docker container
sys.path.insert(0, backend_dir)

from llm import detect_doc_type, generate_reels
from evals import score_reel
from config import REEL_MODEL

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_docs")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "training_data_gold.jsonl")
DB_PATH = os.path.join(backend_dir, "data", "verso.db")

# Expanded preference combos for diversity (8 combos)
PREFERENCE_COMBOS = [
    {"learning_style": "visual", "content_depth": "balanced", "use_case": "learning", "flashcard_difficulty": "medium"},
    {"learning_style": "auditory", "content_depth": "balanced", "use_case": "exam", "flashcard_difficulty": "medium"},
    {"learning_style": "reading", "content_depth": "detailed", "use_case": "research", "flashcard_difficulty": "hard"},
    {"learning_style": "mixed", "content_depth": "brief", "use_case": "work", "flashcard_difficulty": "easy"},
    {"learning_style": "visual", "content_depth": "detailed", "use_case": "exam", "flashcard_difficulty": "hard"},
    {"learning_style": "auditory", "content_depth": "brief", "use_case": "learning", "flashcard_difficulty": "easy"},
    {"learning_style": "reading", "content_depth": "balanced", "use_case": "work", "flashcard_difficulty": "medium"},
    {"learning_style": "mixed", "content_depth": "detailed", "use_case": "research", "flashcard_difficulty": "hard"},
]

# Temperatures to vary per attempt for diversity
TEMPERATURES = [0.3, 0.5, 0.7, 0.4, 0.6]


def load_sample_docs():
    """Load all .txt files from sample_docs directory."""
    if not os.path.exists(SAMPLE_DIR):
        os.makedirs(SAMPLE_DIR)
        print(f"Created {SAMPLE_DIR}/ — add .txt files with sample document text and re-run.")
        sys.exit(1)

    docs = []
    for fname in sorted(os.listdir(SAMPLE_DIR)):
        if fname.endswith(".txt"):
            path = os.path.join(SAMPLE_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                docs.append({"filename": fname, "text": text})

    if not docs:
        print(f"No .txt files found in {SAMPLE_DIR}/. Add sample documents and re-run.")
        sys.exit(1)

    return docs


def load_db_reels(min_score: float) -> list:
    """Load high-scoring reels from the DB that have source_text."""
    if not os.path.exists(DB_PATH):
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT title, summary, narration, category, keywords, source_text "
        "FROM reels WHERE source_text IS NOT NULL AND source_text != ''"
    ).fetchall()
    conn.close()

    gold = []
    for row in rows:
        reel_dict = {
            "reels": [{
                "title": row["title"],
                "summary": row["summary"],
                "narration": row["narration"] or "",
                "category": row["category"] or "",
                "keywords": row["keywords"] or "",
            }],
            "flashcards": [],  # DB reels don't have flashcards inline
        }
        result = score_reel(reel_dict, row["source_text"])
        if result["composite_score"] >= min_score:
            gold.append({
                "input": row["source_text"],
                "output": json.dumps(reel_dict, ensure_ascii=False),
                "score": result["composite_score"],
                "source": "db",
            })

    return gold


def best_of_n(text: str, doc_type: str, prefs: dict, n: int, min_score: float):
    """Generate N candidates, return the best one above min_score (or None)."""
    best = None
    best_score = -1

    for attempt in range(n):
        try:
            result = generate_reels(text[:3000], doc_type, prefs)

            # Skip fallback outputs
            if result["reels"] and result["reels"][0].get("title") == "Summary" and len(result["reels"]) == 1:
                continue

            score_result = score_reel(result, text[:3000], prefs)
            score = score_result["composite_score"]

            if score > best_score:
                best_score = score
                best = result

        except Exception as e:
            print(f"    attempt {attempt+1} error: {e}")

    if best is not None and best_score >= min_score:
        return best, best_score
    return None, best_score


def main():
    parser = argparse.ArgumentParser(description="Best-of-N gold training data generator")
    parser.add_argument("--n", type=int, default=3, help="Number of candidates per input (default: 3)")
    parser.add_argument("--min-score", type=float, default=0.6, help="Minimum composite score to keep (default: 0.6)")
    parser.add_argument("--output", type=str, default=OUTPUT_FILE, help="Output file path")
    args = parser.parse_args()

    print(f"Best-of-{args.n} Gold Data Generator")
    print(f"  Model: {REEL_MODEL}")
    print(f"  Min score: {args.min_score}")
    print(f"  Output: {args.output}")

    # Load sample docs
    docs = load_sample_docs()
    print(f"\nLoaded {len(docs)} sample documents")

    # Collect gold examples from DB first
    db_gold = load_db_reels(args.min_score)
    if db_gold:
        print(f"Found {len(db_gold)} high-scoring reels from DB")

    training_data = []
    total = len(docs) * len(PREFERENCE_COMBOS)
    count = 0
    kept = 0

    for doc in docs:
        doc_type = detect_doc_type(doc["text"])
        print(f"\n{doc['filename']} → doc_type: {doc_type}")

        for prefs in PREFERENCE_COMBOS:
            count += 1
            style = prefs["learning_style"]
            depth = prefs["content_depth"]
            print(f"  [{count}/{total}] {style}+{depth}...", end=" ", flush=True)

            result, score = best_of_n(doc["text"], doc_type, prefs, args.n, args.min_score)

            if result is not None:
                kept += 1
                training_data.append({
                    "input": doc["text"][:3000],
                    "output": json.dumps(result, ensure_ascii=False),
                    "doc_type": doc_type,
                    "learning_style": prefs["learning_style"],
                    "content_depth": prefs["content_depth"],
                    "use_case": prefs["use_case"],
                    "flashcard_difficulty": prefs["flashcard_difficulty"],
                    "source_file": doc["filename"],
                    "score": score,
                    "source": "best_of_n",
                })
                print(f"KEPT (score={score:.3f})")
            else:
                print(f"SKIPPED (best={score:.3f} < {args.min_score})")

    # Add DB gold examples
    training_data.extend(db_gold)

    # Write output
    with open(args.output, "w", encoding="utf-8") as f:
        for item in training_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\n{'='*60}")
    print(f"Done!")
    print(f"  Generated: {kept}/{total} from sample docs")
    print(f"  From DB:   {len(db_gold)} high-scoring reels")
    print(f"  Total:     {len(training_data)} gold examples")
    print(f"  Output:    {args.output}")
    print(f"\nNext: python ../scripts/convert_gold_to_sharegpt.py")


if __name__ == "__main__":
    main()
