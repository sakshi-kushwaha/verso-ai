#!/usr/bin/env python3
"""Seed reels into DB from gold_standard JSON — NO TTS/video needed.

For local algorithm testing only. Inserts reel metadata (title, summary,
narration, category, keywords) without generating audio or video files.

Usage:
    cd backend && python scripts/seed_reels_local.py [--limit N]
"""
import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from database import get_db, init_db

GOLD_JSON = os.path.join(BACKEND_DIR, "data", "gold_standard_reels_3.json")


def main():
    parser = argparse.ArgumentParser(description="Seed reels locally (no TTS/video)")
    parser.add_argument("--limit", type=int, default=10, help="Max reels to seed")
    parser.add_argument("--json", type=str, default=GOLD_JSON, help="Path to gold reels JSON")
    args = parser.parse_args()

    # Load reels
    with open(args.json, encoding="utf-8") as f:
        data = json.load(f)
    reels = data.get("reels", []) if isinstance(data, dict) else data
    reels = reels[: args.limit]

    print(f"Seeding {len(reels)} reels from {args.json}\n")

    # Init DB
    init_db()
    conn = get_db()

    # Get or create seed upload
    row = conn.execute("SELECT id FROM uploads WHERE filename = '__gold_standard__'").fetchone()
    if row:
        upload_id = row[0]
    else:
        cur = conn.execute(
            "INSERT INTO uploads (user_id, filename, status, doc_type, subject_category) "
            "VALUES (1, '__gold_standard__', 'done', 'seed', 'general')"
        )
        conn.commit()
        upload_id = cur.lastrowid

    print(f"Upload ID: {upload_id}\n")

    inserted = 0
    skipped = 0
    for i, reel in enumerate(reels):
        title = reel["title"]

        # Check if already exists
        existing = conn.execute(
            "SELECT id FROM reels WHERE upload_id = ? AND title = ?",
            (upload_id, title),
        ).fetchone()
        if existing:
            print(f"  [{i}] SKIP (exists): {title}")
            skipped += 1
            continue

        conn.execute(
            "INSERT INTO reels (upload_id, title, summary, narration, category, keywords, source_text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                upload_id,
                title,
                reel["summary"],
                reel["narration"],
                reel["category"],
                reel["keywords"],
                reel.get("source_text", reel["summary"]),
            ),
        )
        conn.commit()
        print(f"  [{i}] OK: {title} ({reel['category']})")
        inserted += 1

    conn.close()
    print(f"\nDone! {inserted} inserted, {skipped} skipped")


if __name__ == "__main__":
    main()
