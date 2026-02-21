#!/usr/bin/env python3
"""Generate gold-standard video reels from a pre-written JSON file.

Skips LLM entirely — uses curated narrations, auto-selects stock clips by
category, and renders each reel with multi-clip transitions via compose_multi_clip_reel.

Usage:
    cd backend && python scripts/generate_gold_reels.py [--limit N] [--batch N] [--start N]
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import random
import sys
import time

try:
    import resource
except ImportError:
    resource = None  # Not available on Windows

# Ensure backend/ is on sys.path so we can import project modules
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from database import get_db, init_db
from tts.engine import generate_audio
from video import compose_multi_clip_reel, get_clips_for_category

GOLD_JSON = os.path.join(BACKEND_DIR, "data", "gold_standard_reels_3.json")

SEGMENTS_PER_REEL = 3


def get_rss_mb():
    """Current RSS in megabytes."""
    if resource is None:
        # Windows fallback
        try:
            import psutil
            return psutil.Process().memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0
    usage = resource.getrusage(resource.RUSAGE_SELF)
    if sys.platform == "darwin":
        return usage.ru_maxrss / (1024 * 1024)  # bytes → MB on macOS
    return usage.ru_maxrss / 1024  # KB → MB on Linux


def load_gold_reels(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Support both {"reels": [...]} and bare [...]
    if isinstance(data, dict):
        return data.get("reels", [])
    return data


def auto_select_segments(
    category: str,
    overlays: list[str] | None = None,
    num: int = SEGMENTS_PER_REEL,
) -> list[dict]:
    """Pick `num` random clips from the category's video catalog.

    Returns segment dicts compatible with compose_multi_clip_reel:
        [{"type": "video", "clip": "07.mp4", "duration": 5, "overlay": "text"}, ...]
    """
    clips = get_clips_for_category(category)
    if not clips:
        clips = get_clips_for_category("general")
    if len(clips) <= num:
        chosen = clips[:]
    else:
        chosen = random.sample(clips, num)

    # Distribute duration roughly equally (compose_multi_clip_reel will rescale to TTS length)
    base_dur = 5.0
    segments = []
    for i, c in enumerate(chosen):
        seg = {"type": "video", "clip": c["file"], "duration": base_dur}
        if overlays and i < len(overlays):
            seg["overlay"] = overlays[i]
        segments.append(seg)
    return segments


def ensure_gold_upload(conn) -> int:
    """Get or create the __gold_standard__ upload entry. Returns upload_id."""
    row = conn.execute(
        "SELECT id FROM uploads WHERE filename = '__gold_standard__'"
    ).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO uploads (user_id, filename, status, doc_type, subject_category) "
        "VALUES (1, '__gold_standard__', 'done', 'seed', 'general')"
    )
    conn.commit()
    return cur.lastrowid


def reel_exists(conn, upload_id: int, title: str) -> bool:
    row = conn.execute(
        "SELECT id FROM reels WHERE upload_id = ? AND title = ?",
        (upload_id, title),
    ).fetchone()
    return row is not None


def insert_reel(conn, upload_id: int, reel: dict, video_path: str):
    conn.execute(
        "INSERT INTO reels (upload_id, title, summary, narration, category, keywords, video_path, source_text) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            upload_id,
            reel["title"],
            reel["summary"],
            reel["narration"],
            reel["category"],
            reel["keywords"],
            video_path,
            reel.get("source_text", reel["summary"]),
        ),
    )
    conn.commit()


def process_reel(reel: dict, index: int, upload_id: int, conn) -> bool:
    """Generate TTS audio and compose a multi-clip video reel with transitions.

    Returns True on success, False on failure.
    """
    title = reel["title"]
    narration = reel["narration"]
    category = reel["category"]

    if reel_exists(conn, upload_id, title):
        print(f"  [{index}] SKIP (already exists): {title}")
        return True

    print(f"  [{index}] Processing: {title} ({category})")

    # Auto-select clips from category, attaching overlay texts if present
    overlays = reel.get("overlays", [])
    segments = reel.get("segments") or auto_select_segments(category, overlays=overlays)
    clip_names = [s["clip"] for s in segments]
    overlay_texts = [s.get("overlay", "") for s in segments]
    print(f"    Clips: {clip_names}")
    if any(overlay_texts):
        print(f"    Overlays: {overlay_texts}")

    # 1) TTS
    print(f"    TTS...", end=" ", flush=True)
    try:
        audio_path = generate_audio(narration, reel_index=index)
        if not audio_path or not os.path.exists(audio_path):
            print("FAILED (no audio)")
            return False
        print(f"OK ({os.path.getsize(audio_path) / 1024:.0f}KB)")
    except Exception as e:
        print(f"FAILED ({e})")
        return False

    # 2) Compose multi-clip video with transitions
    print(f"    Video ({len(segments)} segments, xfade transitions)...", end=" ", flush=True)
    try:
        # Use a unique reel_id based on index + offset to avoid cache collisions
        reel_id = 90000 + index
        video_path = compose_multi_clip_reel(
            reel_id=reel_id,
            title=title,
            narration=narration,
            segments=segments,
            category=category,
            tts_audio_path=audio_path,
        )
        if not video_path or not os.path.exists(video_path):
            print("FAILED (no video)")
            return False
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"OK ({size_mb:.1f}MB)")
    except Exception as e:
        print(f"FAILED ({e})")
        return False

    # 3) Insert into DB
    insert_reel(conn, upload_id, reel, video_path)
    print(f"    DB insert OK")
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate gold-standard reels")
    parser.add_argument("--limit", type=int, default=0, help="Max reels to generate (0 = all)")
    parser.add_argument("--batch", type=int, default=5, help="Batch size before GC + cooldown")
    parser.add_argument("--start", type=int, default=0, help="Start index (skip first N reels)")
    parser.add_argument("--json", type=str, default=GOLD_JSON, help="Path to gold reels JSON")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for clip selection")
    args = parser.parse_args()

    random.seed(args.seed)

    print("=== Gold Standard Reel Generator (multi-clip transitions) ===\n")

    # Load reels
    reels = load_gold_reels(args.json)
    total = len(reels)
    print(f"Loaded {total} reels from {args.json}")

    # Apply start/limit
    if args.start > 0:
        reels = reels[args.start:]
        print(f"Starting from index {args.start}")
    if args.limit > 0:
        reels = reels[: args.limit]
        print(f"Limited to {len(reels)} reels")

    # Init DB
    init_db()
    conn = get_db()
    upload_id = ensure_gold_upload(conn)
    print(f"Upload ID: {upload_id}\n")

    ok = 0
    fail = 0
    t0 = time.time()

    for i, reel in enumerate(reels):
        global_idx = i + args.start
        rss = get_rss_mb()
        print(f"\n--- Reel {global_idx + 1}/{total} (RSS: {rss:.0f}MB) ---")

        success = process_reel(reel, global_idx, upload_id, conn)
        if success:
            ok += 1
        else:
            fail += 1

        # Batch cooldown
        if (i + 1) % args.batch == 0 and i + 1 < len(reels):
            gc.collect()
            print(f"\n  [batch pause] GC done, RSS: {get_rss_mb():.0f}MB, sleeping 2s...")
            time.sleep(2)

    conn.close()
    elapsed = time.time() - t0

    print(f"\n{'=' * 50}")
    print(f"Done! {ok} OK, {fail} failed out of {ok + fail} in {elapsed:.0f}s")
    print(f"Final RSS: {get_rss_mb():.0f}MB")


if __name__ == "__main__":
    main()
