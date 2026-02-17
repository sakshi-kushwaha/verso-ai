"""
Convert raw training data to ShareGPT format for Unsloth fine-tuning.

Usage:
    python scripts/convert_to_sharegpt.py

Input:  scripts/training_data_raw.jsonl
Output: scripts/verso_training_sharegpt.json (upload this to Colab)
"""

import json
import os

SCRIPT_DIR = os.path.dirname(__file__)
INPUT_FILE = os.path.join(SCRIPT_DIR, "training_data_raw.jsonl")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "verso_training_sharegpt.json")

SYSTEM_MESSAGE = "You are Verso, a learning content creator. Generate reels and flashcards as JSON."


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Input file not found: {INPUT_FILE}")
        print("Run generate_training_data.py first.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(raw)} raw examples")

    converted = []
    for item in raw:
        user_content = (
            f"Document type: {item['doc_type']}\n"
            f"Learning style: {item['learning_style']}\n"
            f"Depth: {item['content_depth']}\n"
            f"Focus: {item['use_case']}\n"
            f"Difficulty: {item['flashcard_difficulty']}\n"
            f"\nText:\n{item['input']}"
        )

        converted.append({
            "conversations": [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": item["output"]},
            ]
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(converted, f, indent=2, ensure_ascii=False)

    print(f"Converted {len(converted)} examples to ShareGPT format")
    print(f"Output: {OUTPUT_FILE}")
    print(f"\nUpload this file to Google Colab for fine-tuning with Unsloth.")


if __name__ == "__main__":
    main()
