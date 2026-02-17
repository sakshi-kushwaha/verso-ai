"""
Generate training data for fine-tuning Verso's reel/flashcard model.

Usage:
    1. Place sample text files in scripts/sample_docs/ (one .txt per document)
    2. Run on EC2 where Ollama is available:
       cd backend && python ../scripts/generate_training_data.py
    3. Review and curate the output in scripts/training_data_raw.jsonl
    4. Convert to ShareGPT format: python ../scripts/convert_to_sharegpt.py
"""

import json
import sys
import os

# Add backend to path so we can import project modules
backend_dir = os.path.join(os.path.dirname(__file__), "..", "backend")
if not os.path.isdir(backend_dir):
    backend_dir = "/app"  # inside Docker container
sys.path.insert(0, backend_dir)

from llm import detect_doc_type, generate_reels

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_docs")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "training_data_raw.jsonl")

# Preference combinations to generate diverse training examples
PREFERENCE_COMBOS = [
    {"learning_style": "visual", "content_depth": "balanced", "use_case": "learning", "flashcard_difficulty": "medium"},
    {"learning_style": "auditory", "content_depth": "balanced", "use_case": "exam", "flashcard_difficulty": "medium"},
    {"learning_style": "reading", "content_depth": "detailed", "use_case": "research", "flashcard_difficulty": "hard"},
    {"learning_style": "mixed", "content_depth": "brief", "use_case": "work", "flashcard_difficulty": "easy"},
]


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


def main():
    docs = load_sample_docs()
    print(f"Loaded {len(docs)} sample documents")

    training_data = []
    total = len(docs) * len(PREFERENCE_COMBOS)
    count = 0

    for doc in docs:
        doc_type = detect_doc_type(doc["text"])
        print(f"\n{doc['filename']} → doc_type: {doc_type}")

        for prefs in PREFERENCE_COMBOS:
            count += 1
            style = prefs["learning_style"]
            print(f"  [{count}/{total}] Generating: style={style}, depth={prefs['content_depth']}...", end=" ", flush=True)

            try:
                result = generate_reels(doc["text"][:3000], doc_type, prefs)

                # Only keep if JSON parsed successfully (not fallback)
                if result["reels"] and result["reels"][0].get("title") != "Summary":
                    training_data.append({
                        "input": doc["text"][:3000],
                        "output": json.dumps(result, ensure_ascii=False),
                        "doc_type": doc_type,
                        "learning_style": prefs["learning_style"],
                        "content_depth": prefs["content_depth"],
                        "use_case": prefs["use_case"],
                        "flashcard_difficulty": prefs["flashcard_difficulty"],
                        "source_file": doc["filename"],
                    })
                    print(f"OK ({len(result['reels'])} reels, {len(result['flashcards'])} flashcards)")
                else:
                    print("SKIPPED (fallback output)")
            except Exception as e:
                print(f"ERROR: {e}")

    # Write output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for item in training_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\nDone! Generated {len(training_data)} training examples")
    print(f"Output: {OUTPUT_FILE}")
    print(f"\nNext step: Review the output, then run convert_to_sharegpt.py")


if __name__ == "__main__":
    main()
