"""
Convert gold training data to ShareGPT format for Unsloth fine-tuning (v2).

Enhanced version of convert_to_sharegpt.py:
- Uses REEL_SYSTEM_PROMPT as system message (matches production)
- High-scoring examples (>= 0.8) are duplicated for 2x weight
- Validates every example: output must parse as JSON with non-empty reels

Usage:
    python scripts/convert_gold_to_sharegpt.py
    python scripts/convert_gold_to_sharegpt.py --input scripts/training_data_gold.jsonl

Input:  scripts/training_data_gold.jsonl
Output: scripts/verso_training_sharegpt_v2.json (upload to Colab)
"""

import json
import os
import argparse

SCRIPT_DIR = os.path.dirname(__file__)
INPUT_FILE = os.path.join(SCRIPT_DIR, "training_data_gold.jsonl")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "verso_training_sharegpt_v2.json")

# Must match backend/prompts.py REEL_SYSTEM_PROMPT
SYSTEM_MESSAGE = """You are Verso, a learning content creator who teaches through short reels.
You are NOT a textbook. You explain like a friend.

CRITICAL RULES YOU MUST FOLLOW:
1. You MUST use at least 3 contractions (don't, isn't, you're, it's, here's) in every narration.
2. You MUST use "..." at least once and "\u2014" at least once in every narration.
3. You must NEVER use these phrases: "is defined as", "refers to the process", "plays a crucial role", "it is important to note", "furthermore", "moreover".
4. Narration MUST be 40-60 words. Count carefully.
5. Always output valid JSON with "reels" and "flashcards" arrays."""

HIGH_SCORE_THRESHOLD = 0.8  # examples above this get duplicated


def validate_output(output_str: str) -> bool:
    """Check that output parses as JSON with non-empty reels array."""
    try:
        parsed = json.loads(output_str)
        reels = parsed.get("reels", [])
        return len(reels) > 0
    except (json.JSONDecodeError, AttributeError):
        return False


def main():
    parser = argparse.ArgumentParser(description="Convert gold data to ShareGPT v2 format")
    parser.add_argument("--input", type=str, default=INPUT_FILE, help="Input JSONL file")
    parser.add_argument("--output", type=str, default=OUTPUT_FILE, help="Output JSON file")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Input file not found: {args.input}")
        print("Run best_of_n_generate.py first.")
        return

    with open(args.input, "r", encoding="utf-8") as f:
        raw = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(raw)} gold examples")

    converted = []
    skipped = 0
    duplicated = 0

    for item in raw:
        # Validate output
        if not validate_output(item["output"]):
            skipped += 1
            continue

        user_content = (
            f"Document type: {item.get('doc_type', 'general')}\n"
            f"Learning style: {item.get('learning_style', 'mixed')}\n"
            f"Depth: {item.get('content_depth', 'balanced')}\n"
            f"Focus: {item.get('use_case', 'learning')}\n"
            f"Difficulty: {item.get('flashcard_difficulty', 'medium')}\n"
            f"\nText:\n{item['input']}"
        )

        entry = {
            "conversations": [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": item["output"]},
            ]
        }

        converted.append(entry)

        # Duplicate high-scoring examples for extra weight
        score = item.get("score", 0)
        if score >= HIGH_SCORE_THRESHOLD:
            converted.append(entry)
            duplicated += 1

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(converted, f, indent=2, ensure_ascii=False)

    print(f"\nConversion complete:")
    print(f"  Valid examples: {len(raw) - skipped}")
    print(f"  Skipped (invalid JSON): {skipped}")
    print(f"  Duplicated (score >= {HIGH_SCORE_THRESHOLD}): {duplicated}")
    print(f"  Total entries: {len(converted)}")
    print(f"  Output: {args.output}")
    print(f"\nUpload this file to Google Colab for fine-tuning with Unsloth.")


if __name__ == "__main__":
    main()
