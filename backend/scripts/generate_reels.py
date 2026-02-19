#!/usr/bin/env python3
"""Generate video reels from CSV — LLM generates content, ffmpeg composes MP4.

CSV format (videos.csv):
    video_file,description

Flow per row:
    1. LLM generates title, summary, narration, keywords from description + category
    2. Piper TTS generates audio from narration
    3. ffmpeg composes: stock video + TTS audio + background music → MP4
    4. Reel inserted into DB with video_path

Memory-safe for 8GB environments.

Usage:
    cd backend && python scripts/generate_reels.py
    cd backend && python scripts/generate_reels.py --csv data/videos.csv
    cd backend && python scripts/generate_reels.py --batch-size 10 --skip-existing
"""

import argparse
import csv
import gc
import json
import os
import random
import re
import resource
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import STOCK_VIDEOS_DIR, SOUND_EFFECTS_DIR, VIDEO_CACHE_DIR, AUDIO_CACHE_DIR
from database import get_db, init_db
from tts.engine import generate_audio
from llm import generate_mixed_reel_script
from video import compose_reel_video, compose_multi_clip_reel, get_clips_for_category, get_images_for_category

DEFAULT_VIDEOS_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "videos.csv")
DEFAULT_SOUNDS_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "sound_effects.csv")

MAX_RSS_MB = 800
BATCH_COOLDOWN_SEC = 2

# Prompt for LLM to generate reel content from a video description
REEL_CONTENT_PROMPT = """You are an educational content creator. Given a video clip description and its category, generate engaging reel content.

Video description: {description}
Category: {category}

Generate a JSON object with these fields:
- "title": A catchy, concise title (max 60 chars)
- "summary": A 2-3 sentence educational summary about the topic shown in the video (max 200 chars)
- "narration": A 15-second spoken narration script (about 40-50 words) that would be read aloud over the video. Make it engaging, informative, and conversational. Vary your tone — do NOT start every narration the same way.
- "keywords": Comma-separated relevant keywords (3-5 keywords)

IMPORTANT: Return ONLY valid JSON, no other text.

Example:
{{"title": "The Hidden World of Coral Reefs", "summary": "Coral reefs support 25% of marine life despite covering less than 1% of the ocean floor. These living structures are built by tiny organisms over thousands of years.", "narration": "Beneath the waves lies an underwater city teeming with life. Coral reefs may look like rocks, but they are actually built by billions of tiny living creatures. Despite covering less than one percent of the ocean, they support a quarter of all marine species.", "keywords": "coral reefs, marine life, ocean, biodiversity, ecology"}}"""


def get_rss_mb() -> float:
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        if sys.platform == "darwin":
            return usage.ru_maxrss / (1024 * 1024)
        return usage.ru_maxrss / 1024
    except Exception:
        return 0.0


def get_system_memory_mb() -> tuple[float, float]:
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        info = {}
        for line in lines:
            parts = line.split()
            info[parts[0].rstrip(":")] = int(parts[1])
        total = info.get("MemTotal", 0) / 1024
        available = info.get("MemAvailable", 0) / 1024
        return (total - available, total)
    except Exception:
        return (0.0, 0.0)


def memory_ok() -> bool:
    rss = get_rss_mb()
    if rss > MAX_RSS_MB:
        return False
    used, total = get_system_memory_mb()
    if total > 0 and used > total * 0.75:
        return False
    return True


def wait_for_memory(label: str = ""):
    if memory_ok():
        return
    print(f"  [MEM] High memory at {label}, running GC...")
    gc.collect()
    for _ in range(30):
        time.sleep(2)
        gc.collect()
        if memory_ok():
            print("  [MEM] Memory OK, resuming.")
            return
    print("  [MEM] WARNING: Memory still high, continuing anyway.")


def llm_generate_content(description: str, category: str) -> dict:
    """Use LLM to generate title, summary, narration, keywords from video description."""
    from llm import llm_call

    prompt = REEL_CONTENT_PROMPT.format(description=description, category=category)
    result = llm_call(prompt, json_mode=True, timeout=120.0)

    # Parse JSON from response
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", result)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                parsed = {}

    # Validate and provide defaults
    title = parsed.get("title", f"{category} — Quick Reel")[:80]
    summary = parsed.get("summary", description[:200])
    narration = parsed.get("narration", summary)
    keywords = parsed.get("keywords", category.lower())

    return {
        "title": title,
        "summary": summary,
        "narration": narration,
        "keywords": keywords,
    }


def load_videos_csv(path: str) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip(): v.strip() for k, v in row.items()}
            if not row.get("video_file") or not row.get("description"):
                continue
            rows.append(row)
    return rows


def load_sound_effects_csv(path: str) -> list[dict]:
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip(): v.strip() for k, v in row.items()}
            if not row.get("sound_file"):
                continue
            rows.append(row)
    return rows


def process_single_reel(entry: dict, sound_effects: list[dict], upload_id: int) -> dict:
    """Process a single reel: LLM → TTS → compose video → return result."""
    description = entry["description"]
    video_file = entry["video_file"]
    category = video_file.split("/")[0] if "/" in video_file else "general"

    # Resolve stock video path
    stock_video_path = str(STOCK_VIDEOS_DIR / video_file)
    if not os.path.exists(stock_video_path):
        if os.path.exists(video_file):
            stock_video_path = video_file
        else:
            return {"title": video_file, "error": f"Video file not found: {video_file}"}

    # 1. LLM generates content
    try:
        content = llm_generate_content(description, category)
    except Exception as e:
        # Fallback: use description directly
        content = {
            "title": f"{category} Insight",
            "summary": description[:200],
            "narration": description[:200],
            "keywords": category.lower(),
        }
        print(f"  LLM failed ({e}), using fallback content")

    title = content["title"]
    summary = content["summary"]
    narration = content["narration"]
    keywords = content["keywords"]

    # 2. Pick a random sound effect
    sound_effect_path = None
    if sound_effects:
        sfx = random.choice(sound_effects)
        sfx_path = str(SOUND_EFFECTS_DIR / sfx["sound_file"])
        if os.path.exists(sfx_path):
            sound_effect_path = sfx_path

    # 3. Generate TTS from narration
    tts_path = None
    try:
        tts_path = generate_audio(narration)
    except Exception:
        pass

    # 4. Insert reel into DB
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO reels (upload_id, title, summary, narration, category, keywords)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (upload_id, title, summary, narration, category, keywords),
        )
        conn.commit()
        reel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()

    # 5. Compose MP4 — LLM decides segment layout (videos + images)
    try:
        cat_clips = get_clips_for_category(category)
        cat_images = get_images_for_category(category)

        script = None
        if len(cat_clips) >= 2:
            try:
                script = generate_mixed_reel_script(
                    text=description,
                    category=category,
                    clips=cat_clips,
                    images=cat_images,
                )
            except Exception as e:
                print(f"  LLM script failed ({e}), using single-clip fallback")

        if script and script.get("segments"):
            # Use LLM-generated title/narration if available
            script_title = script.get("title") or title
            script_narration = script.get("narration") or narration

            # Re-generate TTS if LLM produced a different narration
            script_tts = tts_path
            if script_narration != narration and script_narration:
                try:
                    script_tts = generate_audio(script_narration)
                except Exception:
                    script_tts = tts_path

            video_path = compose_multi_clip_reel(
                reel_id=reel_id,
                title=script_title,
                narration=script_narration,
                segments=script["segments"],
                category=category,
                tts_audio_path=str(script_tts) if script_tts else None,
                sound_effect_path=sound_effect_path,
            )
        else:
            video_path = compose_reel_video(
                reel_id=reel_id,
                title=title,
                summary=summary,
                stock_video_path=stock_video_path,
                sound_effect_path=sound_effect_path,
                tts_audio_path=str(tts_path) if tts_path else None,
                category=category,
            )

        conn = get_db()
        try:
            conn.execute(
                "UPDATE reels SET video_path = ? WHERE id = ?",
                (video_path, reel_id),
            )
            conn.commit()
        finally:
            conn.close()

        return {"title": title, "reel_id": reel_id, "video_path": video_path}
    except Exception as e:
        return {"title": title, "reel_id": reel_id, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Generate video reels from CSV (8GB safe)")
    parser.add_argument("--csv", default=DEFAULT_VIDEOS_CSV, help="Path to videos CSV")
    parser.add_argument("--sounds", default=DEFAULT_SOUNDS_CSV, help="Path to sound effects CSV")
    parser.add_argument("--batch-size", type=int, default=10, help="Reels per batch before GC pause (default: 10)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip reels whose video_file already has a reel in DB")
    args = parser.parse_args()

    init_db()

    videos = load_videos_csv(args.csv)
    sound_effects = load_sound_effects_csv(args.sounds)

    if not videos:
        print(f"No entries found in {args.csv}")
        return

    print(f"Loaded {len(videos)} video entries, {len(sound_effects)} sound effects")
    print(f"Pipeline: CSV description → LLM content → Piper TTS → ffmpeg MP4")
    print(f"Output: 720x1280 | ffmpeg threads: 2 | batch size: {args.batch_size}")

    VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Create/get upload entry
    conn = get_db()
    upload_row = conn.execute(
        "SELECT id FROM uploads WHERE filename = '__csv_generated__' LIMIT 1"
    ).fetchone()
    if upload_row:
        upload_id = upload_row["id"]
    else:
        conn.execute(
            "INSERT INTO uploads (user_id, filename, status, doc_type) VALUES (1, '__csv_generated__', 'done', 'seed')"
        )
        conn.commit()
        upload_id = conn.execute(
            "SELECT id FROM uploads WHERE filename = '__csv_generated__'"
        ).fetchone()["id"]

    if args.skip_existing:
        existing_titles = {
            row[0] for row in conn.execute("SELECT title FROM reels").fetchall()
        }
        before = len(videos)
        videos = [v for v in videos if v.get("video_file") not in existing_titles]
        skipped = before - len(videos)
        if skipped:
            print(f"Skipping {skipped} already-existing reels")

    conn.close()

    if not videos:
        print("All reels already exist. Nothing to do.")
        return

    # Check LLM availability
    try:
        from llm import llm_call
        llm_call("Say OK", timeout=30.0)
        print("LLM: connected")
    except Exception as e:
        print(f"WARNING: LLM unavailable ({e}). Will use fallback content from descriptions.")

    print(f"\nGenerating {len(videos)} reels...\n")

    start = time.time()
    success = 0
    failed = 0

    for i, entry in enumerate(videos):
        if i > 0 and i % args.batch_size == 0:
            rss = get_rss_mb()
            used, total = get_system_memory_mb()
            mem_info = f"RSS={rss:.0f}MB"
            if total > 0:
                mem_info += f" | System={used:.0f}/{total:.0f}MB ({used/total*100:.0f}%)"
            print(f"\n  --- Batch {i}/{len(videos)} | {mem_info} ---")
            gc.collect()
            wait_for_memory(f"batch {i}")
            time.sleep(BATCH_COOLDOWN_SEC)
            print()

        print(f"[{i+1}/{len(videos)}] {entry['video_file']} ({entry.get('category', '?')})")
        result = process_single_reel(entry, sound_effects, upload_id)
        if "error" in result:
            print(f"  FAILED: {result['error']}")
            failed += 1
        else:
            print(f"  OK → \"{result['title']}\" → reel #{result['reel_id']} → {result['video_path']}")
            success += 1

    elapsed = time.time() - start
    avg = elapsed / len(videos) if videos else 0
    print(f"\nDone in {elapsed:.1f}s ({avg:.1f}s/reel)")
    print(f"{success} succeeded, {failed} failed out of {len(videos)} total")
    print(f"Final RSS: {get_rss_mb():.0f}MB")


if __name__ == "__main__":
    main()
