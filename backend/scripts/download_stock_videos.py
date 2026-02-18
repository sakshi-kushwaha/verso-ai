#!/usr/bin/env python3
"""Download royalty-free stock videos from Pixabay organized by category.

Creates:
  static/stock-videos/{category}/01.mp4 … 05.mp4
  data/videos.csv — master CSV with all downloaded videos

Existing videos (01–03.mp4, originally from Pexels) are kept as-is.
New videos (04–05.mp4) are fetched via the Pixabay API at the smallest
available resolution to save disk space — ffmpeg scales to 720x1280 in video.py.

Usage:
  export PIXABAY_API_KEY="your-key-here"
  cd backend && pip install httpx && python scripts/download_stock_videos.py
"""

import csv
import os
import sys
import time

import httpx

STOCK_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "stock-videos")
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "videos.csv")

API_KEY = os.environ.get("PIXABAY_API_KEY", "")

VIDEOS_PER_CATEGORY = 5

# Descriptions for the existing 3 videos per category (already downloaded from Pexels).
# These are kept so the CSV stays accurate even if the script only downloads new ones.
EXISTING_VIDEOS = {
    "science": [
        "Scientist working in a laboratory examining samples under controlled lighting",
        "Rotating 3D DNA double helix animation with glowing molecular bonds",
        "Two scientists looking through a microscope and discussing findings",
    ],
    "math": [
        "Man writing complex mathematical equations on a large blackboard",
        "Close-up of chalk marks as a man solves a math problem on a blackboard",
        "Woman filling a blackboard with algebraic equations during a lecture",
    ],
    "history": [
        "Time-lapse of clouds rolling over ancient weathered stone ruins",
        "Slow orbit of the sun illuminating Earth's surface from space",
        "Panning shot of ancient artifacts and pottery displayed in a museum",
    ],
    "literature": [
        "Close-up of fingers turning pages of an open book in warm light",
        "Person sitting outdoors reading a paperback book on a sunny day",
        "Man browsing and reading a book in a quiet library aisle",
    ],
    "business": [
        "Team of professionals gathered around a table in a glass conference room",
        "Colleagues leaning over documents during a collaborative business meeting",
        "Overhead shot of a group working on laptops and papers in a meeting room",
    ],
    "technology": [
        "Developer typing lines of code on a dark-themed code editor",
        "Close-up of a monitor displaying JavaScript source code with syntax highlighting",
        "Programmer working across multiple monitors with code and terminal windows",
    ],
    "medicine": [
        "Doctor reviewing an ultrasound image on a medical display monitor",
        "Surgical team performing an operation under bright operating-room lights",
        "Surgeons in sterile gowns and masks working together during surgery",
    ],
    "law": [
        "Close-up of a judge striking a wooden gavel on a sounding block",
        "Brass balance scales and a gavel arranged on a polished wooden desk",
        "Group of lawyers from diverse backgrounds engaged in a round-table discussion",
    ],
    "arts": [
        "Artist stepping back to examine a large colorful painting in a sunlit studio",
        "Hands applying bold brushstrokes of paint to an abstract canvas",
        "Wide shot of an artist working on a painting surrounded by canvases and supplies",
    ],
    "engineering": [
        "Tower cranes swinging steel beams into place on a high-rise construction site",
        "Workers in hard hats assembling a steel tower structure at height",
        "Macro shot of an electronic circuit board with soldered components and copper traces",
    ],
    "general": [
        "Teacher standing at a whiteboard explaining a concept to attentive students",
        "University students taking notes during a lecture in a large auditorium",
        "Students sitting at desks studying and writing in a bright classroom",
    ],
}

# Pixabay search queries per category for downloading new videos (04, 05).
SEARCH_QUERIES = {
    "science": "science laboratory experiment",
    "math": "mathematics equations blackboard",
    "history": "ancient ruins historical",
    "literature": "reading book library",
    "business": "business meeting office",
    "technology": "programming code computer",
    "medicine": "medical doctor hospital",
    "law": "law justice gavel",
    "arts": "painting artist canvas",
    "engineering": "engineering construction building",
    "general": "classroom students education",
}


def search_videos(query, per_page=5):
    """Search Pixabay for videos matching query. Returns list of video hits."""
    url = "https://pixabay.com/api/videos/"
    params = {
        "key": API_KEY,
        "q": query,
        "per_page": per_page,
        "safesearch": "true",
        "order": "popular",
    }
    resp = httpx.get(url, params=params, timeout=30.0)
    if resp.status_code != 200:
        print(f"    API error {resp.status_code}: {resp.text[:200]}")
        return []
    data = resp.json()
    return data.get("hits", [])


def get_smallest_video_url(hit):
    """Extract the smallest video URL from a Pixabay hit.
    Pixabay provides: large (1920), medium (1280), small (960), tiny (640).
    We prefer tiny > small to save space.
    """
    videos = hit.get("videos", {})
    for size in ["tiny", "small", "medium", "large"]:
        entry = videos.get(size, {})
        url = entry.get("url", "")
        if url:
            return url, entry.get("width", 0), entry.get("height", 0)
    return None, 0, 0


def download_video(url, out_path):
    """Download a video from URL to out_path."""
    try:
        with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as resp:
            if resp.status_code != 200:
                return False
            total = 0
            with open(out_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)
                    total += len(chunk)
            if total > 50000:
                return True
            os.unlink(out_path)
    except Exception as e:
        print(f"    Download error: {e}")
        if os.path.exists(out_path):
            os.unlink(out_path)
    return False


def main():
    if not API_KEY:
        print("ERROR: Set PIXABAY_API_KEY environment variable.")
        print("  Get a free key at: https://pixabay.com/api/docs/#api_search_videos")
        print("  export PIXABAY_API_KEY='your-key-here'")
        sys.exit(1)

    existing_count = sum(len(v) for v in EXISTING_VIDEOS.values())
    new_per_cat = VIDEOS_PER_CATEGORY - len(next(iter(EXISTING_VIDEOS.values())))
    new_total = len(SEARCH_QUERIES) * new_per_cat
    print(f"Existing videos: {existing_count} ({len(next(iter(EXISTING_VIDEOS.values())))}/category)")
    print(f"Downloading {new_total} new videos ({new_per_cat}/category) from Pixabay...")
    print(f"Target: static/stock-videos/{{category}}/01.mp4 … {VIDEOS_PER_CATEGORY:02d}.mp4\n")

    os.makedirs(STOCK_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    csv_rows = []
    ok = 0
    fail = 0
    seen_ids = set()

    for category, query in SEARCH_QUERIES.items():
        cat_dir = os.path.join(STOCK_DIR, category)
        os.makedirs(cat_dir, exist_ok=True)
        print(f"\n=== {category} ===")

        # --- Existing videos (01–03) ---
        existing = EXISTING_VIDEOS.get(category, [])
        for idx, description in enumerate(existing):
            filename = f"{idx + 1:02d}.mp4"
            filepath = os.path.join(cat_dir, filename)
            rel_path = f"{category}/{filename}"
            if os.path.exists(filepath) and os.path.getsize(filepath) > 50000:
                size_kb = os.path.getsize(filepath) / 1024
                print(f"  [{idx + 1}] Already exists: {rel_path} ({size_kb:.0f}KB)")
                csv_rows.append({"video_file": rel_path, "description": description})
                ok += 1
            else:
                print(f"  [{idx + 1}] MISSING existing file: {rel_path}")
                fail += 1

        # --- New videos from Pixabay (04–05) ---
        start_idx = len(existing)
        needed = VIDEOS_PER_CATEGORY - start_idx
        if needed <= 0:
            continue

        hits = search_videos(query, per_page=needed + 3)
        if not hits:
            print(f"  No results from Pixabay API for '{query}'")
            fail += needed
            continue

        downloaded = 0
        for hit in hits:
            if downloaded >= needed:
                break

            pixabay_id = hit.get("id")
            if pixabay_id in seen_ids:
                continue
            seen_ids.add(pixabay_id)

            video_url, w, h = get_smallest_video_url(hit)
            if not video_url:
                continue

            idx = start_idx + downloaded + 1
            filename = f"{idx:02d}.mp4"
            filepath = os.path.join(cat_dir, filename)
            rel_path = f"{category}/{filename}"
            description = hit.get("tags", category)

            if os.path.exists(filepath) and os.path.getsize(filepath) > 50000:
                size_kb = os.path.getsize(filepath) / 1024
                print(f"  [{idx}] Already exists: {rel_path} ({size_kb:.0f}KB)")
                csv_rows.append({"video_file": rel_path, "description": description})
                ok += 1
                downloaded += 1
                continue

            print(f"  [{idx}] Pixabay #{pixabay_id} ({w}x{h})...", end=" ", flush=True)
            if download_video(video_url, filepath):
                size_kb = os.path.getsize(filepath) / 1024
                print(f"OK ({size_kb:.0f}KB)")
                csv_rows.append({"video_file": rel_path, "description": description})
                ok += 1
                downloaded += 1
            else:
                print("FAILED")

            time.sleep(0.5)

        fail += needed - downloaded

    # Write CSV
    total = len(SEARCH_QUERIES) * VIDEOS_PER_CATEGORY
    print(f"\nWriting {len(csv_rows)} entries to videos.csv")
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["video_file", "description"])
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"\nDone! {ok} downloaded, {fail} failed out of {total}")


if __name__ == "__main__":
    main()
