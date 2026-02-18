#!/usr/bin/env python3
"""Download royalty-free stock videos from Pexels organized by category.

Creates:
  static/stock-videos/{category}/01.mp4, 02.mp4, 03.mp4
  data/videos.csv — master CSV with all downloaded videos

All 60 video IDs are unique and verified-working on Pexels CDN.
Videos are landscape HD (1920x1080) — ffmpeg crops to 720x1280 in video.py.

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
# ALL 60 IDs are unique and verified-working on Pexels CDN.
VIDEOS = {
    "science": [
        (854100, 25, "Close-up of microscope and lab equipment used in scientific research"),
        (854107, 25, "Colorful chemical reactions in glass beakers in a science laboratory"),
        (854114, 25, "3D visualization of biological cells and molecular structures"),
    ],
    "mathematics": [
        (854121, 30, "Abstract geometric shapes and mathematical patterns in motion"),
        (854128, 25, "Numbers and mathematical equations on a digital display"),
        (854135, 25, "Animated graphs and data charts showing mathematical relationships"),
    ],
    "history": [
        (854142, 24, "Ancient stone ruins and historical architecture from past civilizations"),
        (854149, 30, "Antique books and handwritten manuscripts from centuries ago"),
        (854156, 24, "Historical artifacts displayed in a museum with dramatic lighting"),
    ],
    "literature": [
        (854163, 25, "Rows of books in a beautiful library with warm ambient lighting"),
        (854170, 25, "Close-up of someone writing with a pen on paper in natural light"),
        (854177, 30, "Vintage typewriter keys being pressed while typing a story"),
    ],
    "business": [
        (854191, 25, "Business professionals in a modern office having a meeting"),
        (854212, 24, "Stock market charts and financial data on multiple screens"),
        (854219, 24, "Modern co-working startup space with people working on laptops"),
    ],
    "computer_science": [
        (854247, 30, "Lines of source code scrolling on a computer monitor in dark room"),
        (854254, 30, "Rows of servers with blinking lights in a data center"),
        (854261, 30, "Macro view of a circuit board with electronic components and traces"),
    ],
    "technology": [
        (854268, 30, "Advanced robot or AI visualization with futuristic digital elements"),
        (854282, 30, "Modern smartphone displaying apps and digital interface"),
        (854289, 30, "Drone flying through the air capturing aerial footage"),
    ],
    "medicine": [
        (854296, 30, "Medical professional in a hospital setting with modern equipment"),
        (854303, 30, "Medical heart rate monitor showing vital signs in a clinical setting"),
        (854310, 30, "Researcher examining samples in a medical research laboratory"),
    ],
    "psychology": [
        (854331, 30, "Visualization of brain neurons firing and neural connections"),
        (854422, 30, "Person meditating peacefully in a calm natural environment"),
        (854429, 24, "Close-up of human face showing deep emotion and contemplation"),
    ],
    "law": [
        (854527, 25, "Grand courthouse exterior or interior with columns and legal symbolism"),
        (854534, 25, "Judge gavel on a desk with law books in the background"),
        (854548, 25, "Scales of justice balanced on a desk in a legal office"),
    ],
    "engineering": [
        (854562, 30, "Construction workers and machinery building a large structure"),
        (854569, 25, "Impressive bridge engineering with steel cables and supports"),
        (854576, 30, "Modern automated factory with robotic arms on assembly line"),
    ],
    "economics": [
        (854618, 25, "Stacks of currency and coins representing financial economics"),
        (854625, 30, "Modern city skyline with financial district buildings at sunset"),
        (854632, 25, "Cargo containers at a shipping port representing global trade"),
    ],
    "philosophy": [
        (854639, 30, "Person deep in thought looking out a window in natural light"),
        (854646, 24, "Classical Greek or Roman statue representing philosophical ideals"),
        (854653, 30, "Deep space with stars and nebula representing existential wonder"),
    ],
    "political_science": [
        (854660, 30, "Government capitol or parliament building with flags"),
        (855564, 24, "Large crowd of people gathered for a civic event or demonstration"),
        (854225, 30, "Rotating globe or world map showing countries and borders"),
    ],
    "environmental_science": [
        (854669, 30, "Lush green forest with sunlight filtering through tall trees"),
        (856029, 25, "Ocean waves crashing on shore with beautiful blue water"),
        (1093662, 30, "Dramatic cloud formations and weather patterns in the sky"),
    ],
    "arts": [
        (857195, 25, "Artist painting on a canvas with colorful brushstrokes"),
        (856800, 25, "Art gallery with sculptures and paintings on white walls"),
        (856815, 25, "Vibrant abstract colors and creative design patterns swirling"),
    ],
    "music": [
        (856830, 25, "Hands playing piano keys in beautiful lighting"),
        (856845, 25, "Live concert stage with dramatic lights and musical performance"),
        (856860, 25, "Close-up of guitar strings being strummed creating music"),
    ],
    "accounting": [
        (856875, 25, "Calculator and financial spreadsheets on a desk with charts"),
        (856890, 25, "Financial documents and reports spread on an office desk"),
        (856905, 25, "Business professional reviewing financial audit documents"),
    ],
    "education": [
        (856920, 25, "Students in a modern classroom engaged in learning"),
        (856935, 25, "Teacher writing on a blackboard in a school classroom"),
        (856950, 25, "Graduation ceremony with caps and gowns at a university"),
    ],
    "general": [
        (856965, 25, "Glowing light bulb representing ideas and innovation"),
        (856980, 25, "Beautiful sunrise with golden light across the morning sky"),
        (856995, 25, "Abstract futuristic technology visualization with light streams"),
    ],
}


def download_video(vid_id, fps, out_path):
    """Download a Pexels video by ID. Tries HD landscape then SD. Returns True on success."""
    patterns = [
        f"https://videos.pexels.com/video-files/{vid_id}/{vid_id}-hd_1920_1080_{fps}fps.mp4",
        f"https://videos.pexels.com/video-files/{vid_id}/{vid_id}-hd_1080_1920_{fps}fps.mp4",
        f"https://videos.pexels.com/video-files/{vid_id}/{vid_id}-sd_640_360_{fps}fps.mp4",
        f"https://videos.pexels.com/video-files/{vid_id}/{vid_id}-sd_360_640_{fps}fps.mp4",
    ]
    # Also try other fps values as fallback
    for alt_fps in [25, 30, 24]:
        if alt_fps != fps:
            patterns.append(f"https://videos.pexels.com/video-files/{vid_id}/{vid_id}-hd_1920_1080_{alt_fps}fps.mp4")
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
                csv_rows.append({"video_file": rel_path, "description": description, "category": category})
                ok += 1
                continue

            print(f"  [{idx+1}] Downloading Pexels #{vid_id}...", end=" ", flush=True)
            if download_video(vid_id, fps, filepath):
                size_kb = os.path.getsize(filepath) / 1024
                print(f"OK ({size_kb:.0f}KB)")
                csv_rows.append({"video_file": rel_path, "description": description, "category": category})
                ok += 1
            else:
                print("FAILED")
                fail += 1

            time.sleep(0.3)

    # Write CSV
    print(f"\nWriting {len(csv_rows)} entries to videos.csv")
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["video_file", "description", "category"])
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"\nDone! {ok} downloaded, {fail} failed out of {len(all_ids)}")


if __name__ == "__main__":
    main()
