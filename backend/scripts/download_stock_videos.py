#!/usr/bin/env python3
"""Download royalty-free stock videos from Pixabay organized by category.

Creates:
  static/stock-videos/{category}/01.mp4 … 20.mp4
  data/videos.csv — master CSV with all downloaded videos

Existing videos (01–03.mp4, originally from Pexels) are kept as-is.
Videos 04–05 use the first set of Pixabay queries.
Videos 06–10 use a second set of queries for variety.
Videos 11–20 use a third set of queries for even more variety.
All fetched at smallest available resolution — ffmpeg scales to 720x1280 in video.py.

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

VIDEOS_PER_CATEGORY = 20

# Descriptions for the existing 3 videos per category (already downloaded from Pexels).
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

# Pixabay search queries per category — three rounds for variety.
# Round 1 was used for videos 04-05.
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

# Round 2 adds videos 06-10.
SEARCH_QUERIES_ROUND2 = {
    "science": "space planets astronomy",
    "math": "geometry shapes numbers",
    "history": "old maps world war",
    "literature": "writing pen typewriter",
    "business": "stock market finance chart",
    "technology": "robot artificial intelligence",
    "medicine": "pharmacy pills medicine bottles",
    "law": "court trial lawyer judge",
    "arts": "sculpture museum gallery",
    "engineering": "robotics factory automation",
    "general": "university campus lecture hall",
}

# Round 3 adds videos 11-20 — fresh queries for maximum variety.
SEARCH_QUERIES_ROUND3 = {
    "science": [
        ("chemistry beaker reaction", 5),
        ("biology cells microscope", 5),
    ],
    "math": [
        ("calculator statistics data", 5),
        ("fractal abstract pattern", 5),
    ],
    "history": [
        ("castle medieval fortress", 5),
        ("ancient egypt pyramids", 5),
    ],
    "literature": [
        ("bookshelf library shelves", 5),
        ("poetry scroll parchment", 5),
    ],
    "business": [
        ("startup entrepreneur laptop", 5),
        ("handshake deal partnership", 5),
    ],
    "technology": [
        ("server data center cloud", 5),
        ("smartphone mobile app", 5),
    ],
    "medicine": [
        ("stethoscope heartbeat checkup", 5),
        ("laboratory blood test", 5),
    ],
    "law": [
        ("police crime investigation", 5),
        ("prison jail cell bars", 5),
    ],
    "arts": [
        ("pottery clay hands craft", 5),
        ("dance ballet performance stage", 5),
    ],
    "engineering": [
        ("bridge architecture steel", 5),
        ("3d printing prototype", 5),
    ],
    "general": [
        ("library books study", 5),
        ("graduation ceremony diploma", 5),
    ],
}

# Pre-written descriptions for videos 04-05 (previously just had category name).
DESCRIPTIONS_04_05 = {
    "science": [
        "Scientist conducting an experiment in a research laboratory",
        "Scientific instruments and equipment in a modern lab setting",
    ],
    "math": [
        "Mathematical formulas and equations written on a chalkboard",
        "Abstract mathematical concepts visualized on a board",
    ],
    "history": [
        "Historic landmarks and architecture from a bygone era",
        "Ancient historical site with weathered stone structures",
    ],
    "literature": [
        "Books arranged on shelves in a cozy reading environment",
        "Pages of a book fluttering in soft ambient light",
    ],
    "business": [
        "Business professionals collaborating in a modern office space",
        "Corporate meeting with team members discussing strategy",
    ],
    "technology": [
        "Computer screen showing software development environment",
        "Technology workspace with multiple screens and digital interfaces",
    ],
    "medicine": [
        "Medical professional examining patient records in a hospital",
        "Healthcare setting with medical equipment and instruments",
    ],
    "law": [
        "Legal documents and gavel on a courtroom desk",
        "Scales of justice and legal books in a law office setting",
    ],
    "arts": [
        "Art gallery with colorful paintings and creative installations",
        "Creative art studio with brushes and canvases in warm light",
    ],
    "engineering": [
        "Engineering blueprints and construction planning in progress",
        "Heavy machinery and structural framework at a building site",
    ],
    "general": [
        "Students engaged in a group study session on campus",
        "Classroom setting with students listening to an educational lecture",
    ],
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


def make_description(tags):
    """Convert raw Pixabay tags into a clean sentence-style description."""
    if not tags:
        return ""
    tag_list = [t.strip() for t in tags.split(",")][:6]
    # Capitalize first tag, join with commas
    if len(tag_list) == 1:
        return tag_list[0].capitalize() + " footage"
    main = tag_list[0].capitalize()
    rest = ", ".join(tag_list[1:])
    return f"{main} with {rest}"


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


def download_round(category, cat_dir, query, needed, start_idx, seen_ids, csv_rows):
    """Download a batch of videos for a given query. Returns (ok, fail) counts."""
    ok = 0
    fail = 0
    next_idx = start_idx

    hits = search_videos(query, per_page=needed + 5)
    if not hits:
        print(f"  No results from Pixabay API for '{query}'")
        return 0, needed

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

        filename = f"{next_idx:02d}.mp4"
        filepath = os.path.join(cat_dir, filename)
        rel_path = f"{category}/{filename}"
        description = make_description(hit.get("tags", category))

        if os.path.exists(filepath) and os.path.getsize(filepath) > 50000:
            size_kb = os.path.getsize(filepath) / 1024
            print(f"  [{next_idx}] Already exists: {rel_path} ({size_kb:.0f}KB)")
            csv_rows.append({"video_file": rel_path, "description": description})
            ok += 1
            downloaded += 1
            next_idx += 1
            continue

        print(f"  [{next_idx}] Pixabay #{pixabay_id} ({w}x{h})...", end=" ", flush=True)
        if download_video(video_url, filepath):
            size_kb = os.path.getsize(filepath) / 1024
            print(f"OK ({size_kb:.0f}KB)")
            csv_rows.append({"video_file": rel_path, "description": description})
            ok += 1
            downloaded += 1
            next_idx += 1
        else:
            print("FAILED")
            next_idx += 1

        time.sleep(0.5)

    fail += needed - downloaded
    return ok, fail


def main():
    if not API_KEY:
        print("ERROR: Set PIXABAY_API_KEY environment variable.")
        print("  Get a free key at: https://pixabay.com/api/docs/#api_search_videos")
        print("  export PIXABAY_API_KEY='your-key-here'")
        sys.exit(1)

    print(f"Target: static/stock-videos/{{category}}/01.mp4 … {VIDEOS_PER_CATEGORY:02d}.mp4")
    print(f"Downloading up to {VIDEOS_PER_CATEGORY} videos per category from Pixabay...\n")

    os.makedirs(STOCK_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    csv_rows = []
    ok = 0
    fail = 0
    seen_ids = set()

    for category in SEARCH_QUERIES:
        cat_dir = os.path.join(STOCK_DIR, category)
        os.makedirs(cat_dir, exist_ok=True)
        print(f"\n=== {category} ===")

        # --- Existing Pexels videos (01–03) ---
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

        # --- Keep existing Pixabay videos (04–05) with proper descriptions ---
        descs_04_05 = DESCRIPTIONS_04_05.get(category, [category, category])
        for i, idx in enumerate(range(len(existing) + 1, 6)):  # 04, 05
            filename = f"{idx:02d}.mp4"
            filepath = os.path.join(cat_dir, filename)
            rel_path = f"{category}/{filename}"
            desc = descs_04_05[i] if i < len(descs_04_05) else category
            if os.path.exists(filepath) and os.path.getsize(filepath) > 50000:
                size_kb = os.path.getsize(filepath) / 1024
                print(f"  [{idx}] Already exists: {rel_path} ({size_kb:.0f}KB)")
                csv_rows.append({"video_file": rel_path, "description": desc})
                ok += 1
            else:
                print(f"  [{idx}] MISSING: {rel_path}")
                fail += 1

        # --- Round 2 downloads (06–10) ---
        query = SEARCH_QUERIES_ROUND2.get(category, "")
        if query:
            r_ok, r_fail = download_round(category, cat_dir, query, 5, 6, seen_ids, csv_rows)
            ok += r_ok
            fail += r_fail

        # --- Round 3 downloads (11–20) ---
        round3_queries = SEARCH_QUERIES_ROUND3.get(category, [])
        next_idx = 11
        for query, count in round3_queries:
            r_ok, r_fail = download_round(category, cat_dir, query, count, next_idx, seen_ids, csv_rows)
            ok += r_ok
            fail += r_fail
            next_idx += count

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
