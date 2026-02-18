#!/usr/bin/env python3
"""Download royalty-free stock videos from Pexels organized by category.

Creates:
  static/stock-videos/{category}/01.mp4, 02.mp4, 03.mp4
  data/videos.csv — master CSV with all downloaded videos

All 33 video IDs are unique and verified-working on Pexels CDN (SD).
Videos are SD only (640x360) to save disk space — ffmpeg scales to 720x1280 in video.py.

Usage:
  cd backend && pip install httpx && python scripts/download_stock_videos.py
"""

import csv
import os
import sys
import time

import httpx

STOCK_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "stock-videos")
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "videos.csv")

# Each entry: (pexels_id, fps, description)
# 33 IDs across the 11 app categories — SD only (640x360).
# Categories match bg_images.py: science, math, history, literature, business,
# technology, medicine, law, arts, engineering, general.
VIDEOS = {
    "science": [
        (4121322, 25, "Scientist working in a laboratory examining samples under controlled lighting"),
        (3191420, 25, "Rotating 3D DNA double helix animation with glowing molecular bonds"),
        (3196600, 25, "Two scientists looking through a microscope and discussing findings"),
    ],
    "math": [
        (3196292, 25, "Man writing complex mathematical equations on a large blackboard"),
        (3196291, 25, "Close-up of chalk marks as a man solves a math problem on a blackboard"),
        (3196425, 25, "Woman filling a blackboard with algebraic equations during a lecture"),
    ],
    "history": [
        (855603, 25, "Time-lapse of clouds rolling over ancient weathered stone ruins"),
        (1851190, 25, "Slow orbit of the sun illuminating Earth's surface from space"),
        (4335825, 24, "Panning shot of ancient artifacts and pottery displayed in a museum"),
    ],
    "literature": [
        (4625318, 25, "Close-up of fingers turning pages of an open book in warm light"),
        (2795307, 25, "Person sitting outdoors reading a paperback book on a sunny day"),
        (6550654, 25, "Man browsing and reading a book in a quiet library aisle"),
    ],
    "business": [
        (3205624, 25, "Team of professionals gathered around a table in a glass conference room"),
        (3252123, 25, "Colleagues leaning over documents during a collaborative business meeting"),
        (3209301, 25, "Overhead shot of a group working on laptops and papers in a meeting room"),
    ],
    "technology": [
        (854053, 25, "Developer typing lines of code on a dark-themed code editor"),
        (11274341, 25, "Close-up of a monitor displaying JavaScript source code with syntax highlighting"),
        (6964235, 25, "Programmer working across multiple monitors with code and terminal windows"),
    ],
    "medicine": [
        (855481, 25, "Doctor reviewing an ultrasound image on a medical display monitor"),
        (4976176, 25, "Surgical team performing an operation under bright operating-room lights"),
        (3197622, 25, "Surgeons in sterile gowns and masks working together during surgery"),
    ],
    "law": [
        (6699964, 24, "Close-up of a judge striking a wooden gavel on a sounding block"),
        (5636977, 24, "Brass balance scales and a gavel arranged on a polished wooden desk"),
        (4479793, 25, "Group of lawyers from diverse backgrounds engaged in a round-table discussion"),
    ],
    "arts": [
        (6214507, 25, "Artist stepping back to examine a large colorful painting in a sunlit studio"),
        (4807906, 25, "Hands applying bold brushstrokes of paint to an abstract canvas"),
        (8037499, 25, "Wide shot of an artist working on a painting surrounded by canvases and supplies"),
    ],
    "engineering": [
        (855271, 25, "Tower cranes swinging steel beams into place on a high-rise construction site"),
        (856439, 25, "Workers in hard hats assembling a steel tower structure at height"),
        (3866849, 25, "Macro shot of an electronic circuit board with soldered components and copper traces"),
    ],
    "general": [
        (5198159, 25, "Teacher standing at a whiteboard explaining a concept to attentive students"),
        (8198517, 25, "University students taking notes during a lecture in a large auditorium"),
        (8342354, 25, "Students sitting at desks studying and writing in a bright classroom"),
    ],
}


def download_video(vid_id, fps, out_path):
    """Download a Pexels video by ID. SD only to save disk space."""
    patterns = [
        f"https://videos.pexels.com/video-files/{vid_id}/{vid_id}-sd_640_360_{fps}fps.mp4",
        f"https://videos.pexels.com/video-files/{vid_id}/{vid_id}-sd_360_640_{fps}fps.mp4",
    ]
    # Also try other fps values as fallback
    for alt_fps in [25, 30, 24]:
        if alt_fps != fps:
            patterns.append(f"https://videos.pexels.com/video-files/{vid_id}/{vid_id}-sd_640_360_{alt_fps}fps.mp4")

    for url in patterns:
        try:
            with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as resp:
                if resp.status_code != 200:
                    continue
                total = 0
                with open(out_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        total += len(chunk)
                if total > 50000:
                    return True
                os.unlink(out_path)
        except Exception:
            if os.path.exists(out_path):
                os.unlink(out_path)
    return False


def main():
    # Verify uniqueness
    all_ids = []
    for entries in VIDEOS.values():
        for vid_id, _, _ in entries:
            all_ids.append(vid_id)
    assert len(all_ids) == len(set(all_ids)), f"Duplicate IDs! {len(all_ids)} total, {len(set(all_ids))} unique"

    print(f"Downloading {len(all_ids)} unique stock videos for {len(VIDEOS)} categories...")
    print(f"Target: static/stock-videos/{{category}}/01.mp4\n")

    os.makedirs(STOCK_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    csv_rows = []
    ok = 0
    fail = 0

    for category, entries in VIDEOS.items():
        cat_dir = os.path.join(STOCK_DIR, category)
        os.makedirs(cat_dir, exist_ok=True)
        print(f"\n=== {category} ===")

        for idx, (vid_id, fps, description) in enumerate(entries):
            filename = f"{idx+1:02d}.mp4"
            filepath = os.path.join(cat_dir, filename)
            rel_path = f"{category}/{filename}"

            if os.path.exists(filepath) and os.path.getsize(filepath) > 50000:
                size_kb = os.path.getsize(filepath) / 1024
                print(f"  [{idx+1}] Already exists: {rel_path} ({size_kb:.0f}KB)")
                csv_rows.append({"video_file": rel_path, "description": description})
                ok += 1
                continue

            print(f"  [{idx+1}] Downloading Pexels #{vid_id}...", end=" ", flush=True)
            if download_video(vid_id, fps, filepath):
                size_kb = os.path.getsize(filepath) / 1024
                print(f"OK ({size_kb:.0f}KB)")
                csv_rows.append({"video_file": rel_path, "description": description})
                ok += 1
            else:
                print("FAILED")
                fail += 1

            time.sleep(0.3)

    # Write CSV
    print(f"\nWriting {len(csv_rows)} entries to videos.csv")
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["video_file", "description"])
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"\nDone! {ok} downloaded, {fail} failed out of {len(all_ids)}")


if __name__ == "__main__":
    main()
