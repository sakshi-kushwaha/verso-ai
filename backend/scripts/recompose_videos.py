#!/usr/bin/env python3
"""Recompose all existing reel videos with current video.py code.

Deletes cached video files and regenerates them. Use this after updating
caption styles, animations, or composition logic.

Usage:
    cd backend && python scripts/recompose_videos.py [--limit N] [--batch N]
"""
from __future__ import annotations

import argparse
import gc
import os
import re
import sys
import time

try:
    import resource
except ImportError:
    resource = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from database import get_db, init_db
from tts.engine import generate_audio
from video import compose_multi_clip_reel, get_clips_for_category, VIDEO_CACHE_DIR
import random


def get_rss_mb():
    if resource is None:
        try:
            import psutil
            return psutil.Process().memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0
    usage = resource.getrusage(resource.RUSAGE_SELF)
    if sys.platform == "darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024


def recompose_reel(reel_id: int, title: str, narration: str, category: str) -> bool:
    """Delete cached video and recompose with current code. Returns True on success."""
    # Find and delete cached video
    possible_paths = [
        VIDEO_CACHE_DIR / f"reel_{reel_id}.mp4",
    ]
    # Gold standard reels also use reel_90000+ naming
    for p in possible_paths:
        if p.exists():
            p.unlink()
            print(f"    Deleted cache: {p.name}")

    # Clean narration for TTS
    clean_narration = re.sub(r'\*+', '', narration).strip()
    if not clean_narration:
        print(f"    SKIP (no narration)")
        return False

    # Generate TTS
    print(f"    TTS...", end=" ", flush=True)
    try:
        audio_path = generate_audio(clean_narration, reel_index=reel_id)
        if not audio_path or not os.path.exists(audio_path):
            print("FAILED (no audio)")
            return False
        print(f"OK", end=" ", flush=True)
    except Exception as e:
        print(f"FAILED ({e})")
        return False

    # Auto-select 3 clips from category
    clips = get_clips_for_category(category or "general")
    if not clips:
        print("FAILED (no clips)")
        return False
    chosen = random.sample(clips, min(3, len(clips)))
    segments = [{"type": "video", "clip": c["file"], "duration": 5.0} for c in chosen]

    # Compose video
    print(f"Video...", end=" ", flush=True)
    try:
        video_path = compose_multi_clip_reel(
            reel_id=reel_id,
            title=title,
            narration=clean_narration,
            segments=segments,
            category=category or "general",
            tts_audio_path=str(audio_path),
        )
        if not video_path or not os.path.exists(video_path):
            print("FAILED (no output)")
            return False
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"OK ({size_mb:.1f}MB)")
    except Exception as e:
        print(f"FAILED ({e})")
        return False

    # Update DB with new video path
    conn = get_db()
    conn.execute("UPDATE reels SET video_path = ? WHERE id = ?", (video_path, reel_id))
    conn.commit()
    conn.close()
    return True


def main():
    parser = argparse.ArgumentParser(description="Recompose all reel videos")
    parser.add_argument("--limit", type=int, default=0, help="Max reels (0 = all)")
    parser.add_argument("--batch", type=int, default=5, help="Batch size before GC pause")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)
    init_db()

    conn = get_db()
    reels = conn.execute(
        "SELECT id, title, narration, category, video_path FROM reels "
        "WHERE video_path IS NOT NULL AND narration IS NOT NULL AND narration != '' "
        "ORDER BY id"
    ).fetchall()
    conn.close()

    if args.limit > 0:
        reels = reels[:args.limit]

    print(f"=== Recompose {len(reels)} reel videos ===\n")

    ok = fail = 0
    t0 = time.time()

    for i, r in enumerate(reels):
        rss = get_rss_mb()
        print(f"\n[{i+1}/{len(reels)}] Reel {r['id']}: {r['title'][:50]} (RSS: {rss:.0f}MB)")

        # For gold standard reels, the video_path contains reel_90000+ naming
        # Extract the actual reel_id used in the filename
        vp = r["video_path"] or ""
        if "reel_9000" in vp:
            # Gold standard reel — extract the 90000+ id from filename
            import re as re2
            m = re2.search(r'reel_(\d+)\.mp4', vp)
            compose_id = int(m.group(1)) if m else r["id"]
        else:
            compose_id = r["id"]

        if recompose_reel(compose_id, r["title"], r["narration"], r["category"]):
            ok += 1
        else:
            fail += 1

        if (i + 1) % args.batch == 0 and i + 1 < len(reels):
            gc.collect()
            print(f"\n  [batch] GC done, RSS: {get_rss_mb():.0f}MB, sleeping 2s...")
            time.sleep(2)

    elapsed = time.time() - t0
    print(f"\n{'='*50}")
    print(f"Done! {ok} OK, {fail} failed in {elapsed:.0f}s")


if __name__ == "__main__":
    main()
