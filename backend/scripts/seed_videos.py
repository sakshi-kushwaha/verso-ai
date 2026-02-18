#!/usr/bin/env python3
"""Seed 3-5 video reels with pre-downloaded stock assets.

Usage:
    cd backend && python scripts/seed_videos.py
"""

import os
import sys

# Add backend root to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import STOCK_VIDEOS_DIR, SOUND_EFFECTS_DIR, VIDEO_CACHE_DIR, AUDIO_CACHE_DIR
from database import get_db, init_db
from tts.engine import generate_audio
from video import compose_reel_video

# Hardcoded educational reels
SEED_REELS = [
    {
        "title": "The Water Cycle Explained",
        "summary": (
            "Water continuously moves through Earth in a process called the water cycle. "
            "It evaporates from oceans and lakes, forms clouds through condensation, "
            "and returns as precipitation — rain, snow, or hail. This cycle is essential "
            "for all life on Earth and drives weather patterns across the globe."
        ),
        "narration": (
            "Did you know that every drop of water you drink has been recycled billions of times? "
            "The water cycle is nature's way of purifying and redistributing water. "
            "It starts with evaporation from oceans, lakes, and rivers. "
            "Water vapor rises, cools, and condenses into clouds. "
            "Eventually, it falls back as rain or snow. This cycle powers our weather "
            "and sustains all living things on Earth."
        ),
        "category": "Science",
        "keywords": "water cycle, evaporation, condensation, precipitation, earth science",
        "stock_video": "nature_water.mp4",
        "sound_effect": "chime.mp3",
    },
    {
        "title": "How Photosynthesis Works",
        "summary": (
            "Plants convert sunlight into food through photosynthesis. Using chlorophyll "
            "in their leaves, they absorb carbon dioxide and water to produce glucose and oxygen. "
            "This process is the foundation of nearly all food chains on Earth."
        ),
        "narration": (
            "Photosynthesis is one of the most important chemical reactions on our planet. "
            "Plants absorb sunlight using a green pigment called chlorophyll. "
            "They take in carbon dioxide from the air and water from the soil. "
            "Using light energy, they convert these into glucose for food and release oxygen. "
            "Without photosynthesis, there would be no oxygen for us to breathe."
        ),
        "category": "Biology",
        "keywords": "photosynthesis, plants, chlorophyll, oxygen, biology",
        "stock_video": "science_lab.mp4",
        "sound_effect": "chime.mp3",
    },
    {
        "title": "The Solar System at a Glance",
        "summary": (
            "Our solar system has eight planets orbiting the Sun. The four inner rocky planets — "
            "Mercury, Venus, Earth, and Mars — are smaller and denser. The four outer gas giants — "
            "Jupiter, Saturn, Uranus, and Neptune — are massive and surrounded by rings and moons."
        ),
        "narration": (
            "Welcome to a quick tour of our solar system. "
            "Closest to the Sun are the four rocky planets: Mercury, Venus, Earth, and Mars. "
            "Beyond the asteroid belt lie the gas giants: Jupiter, the largest planet, "
            "Saturn with its spectacular rings, and the ice giants Uranus and Neptune. "
            "Our solar system also contains dwarf planets, asteroids, and countless comets."
        ),
        "category": "Astronomy",
        "keywords": "solar system, planets, astronomy, space, sun",
        "stock_video": "space_earth.mp4",
        "sound_effect": "chime.mp3",
    },
    {
        "title": "Understanding the Pythagorean Theorem",
        "summary": (
            "The Pythagorean theorem states that in a right triangle, the square of the hypotenuse "
            "equals the sum of the squares of the other two sides: a² + b² = c². "
            "This fundamental relationship is used everywhere from architecture to navigation."
        ),
        "narration": (
            "The Pythagorean theorem is one of the most famous formulas in mathematics. "
            "In any right triangle, if you square the two shorter sides and add them together, "
            "you get the square of the longest side, called the hypotenuse. "
            "Written as a squared plus b squared equals c squared. "
            "Builders use this to ensure corners are perfectly square. "
            "Navigators use it to calculate distances. It is everywhere."
        ),
        "category": "Mathematics",
        "keywords": "pythagorean theorem, geometry, triangles, math, algebra",
        "stock_video": "math_geometry.mp4",
        "sound_effect": "chime.mp3",
    },
    {
        "title": "The Story of the Printing Press",
        "summary": (
            "Johannes Gutenberg invented the movable-type printing press around 1440. "
            "This revolutionary device made books affordable and accessible, sparking the "
            "spread of knowledge across Europe. It is considered one of the most important "
            "inventions in human history."
        ),
        "narration": (
            "Before the printing press, every book had to be copied by hand — "
            "a process that could take months. In 1440, Johannes Gutenberg changed everything. "
            "His movable-type printing press could produce pages quickly and cheaply. "
            "Within decades, millions of books were in circulation. "
            "This sparked the Renaissance, the Reformation, and the Scientific Revolution. "
            "The printing press truly transformed the world."
        ),
        "category": "History",
        "keywords": "printing press, Gutenberg, history, books, Renaissance",
        "stock_video": "books_library.mp4",
        "sound_effect": "chime.mp3",
    },
]

SEED_MARKER = "__verso_video_seed__"


def main():
    init_db()
    conn = get_db()

    # Check if already seeded (idempotent)
    existing = conn.execute(
        "SELECT COUNT(*) FROM reels WHERE keywords LIKE ?",
        (f"%{SEED_MARKER}%",)
    ).fetchone()[0]

    if existing >= len(SEED_REELS):
        print(f"Already seeded ({existing} video reels found). Skipping.")
        conn.close()
        return

    # We need a user to associate with — use the default seed user (id=1)
    # Also need an upload — create a dummy one for seed reels
    upload_row = conn.execute(
        "SELECT id FROM uploads WHERE filename = '__seed_videos__' LIMIT 1"
    ).fetchone()

    if upload_row:
        upload_id = upload_row["id"]
    else:
        conn.execute(
            "INSERT INTO uploads (user_id, filename, status, doc_type) VALUES (1, '__seed_videos__', 'done', 'seed')"
        )
        conn.commit()
        upload_id = conn.execute(
            "SELECT id FROM uploads WHERE filename = '__seed_videos__'"
        ).fetchone()["id"]

    VIDEO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    for i, reel in enumerate(SEED_REELS):
        print(f"\n[{i+1}/{len(SEED_REELS)}] Processing: {reel['title']}")

        # Check if this specific reel already exists
        exists = conn.execute(
            "SELECT id FROM reels WHERE title = ? AND keywords LIKE ?",
            (reel["title"], f"%{SEED_MARKER}%")
        ).fetchone()
        if exists:
            print(f"  → Already exists (id={exists['id']}), skipping.")
            continue

        # 1. Generate TTS audio
        print("  → Generating TTS audio...")
        try:
            tts_path = generate_audio(reel["narration"])
            print(f"  → TTS saved: {tts_path}")
        except Exception as e:
            print(f"  → TTS failed ({e}), continuing without narration audio")
            tts_path = None

        # 2. Resolve asset paths
        stock_video_path = str(STOCK_VIDEOS_DIR / reel["stock_video"])
        sound_effect_path = str(SOUND_EFFECTS_DIR / reel["sound_effect"])

        if not os.path.exists(stock_video_path):
            print(f"  → WARNING: Stock video not found: {stock_video_path}")
            print("  → Skipping video composition.")
            video_path = None
        else:
            # Insert reel first to get an ID for the video filename
            tagged_keywords = f"{reel['keywords']}, {SEED_MARKER}"
            conn.execute(
                """INSERT INTO reels (upload_id, title, summary, narration, category, keywords)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (upload_id, reel["title"], reel["summary"], reel["narration"],
                 reel["category"], tagged_keywords),
            )
            conn.commit()
            reel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # 3. Compose video
            print("  → Composing video reel...")
            try:
                video_path = compose_reel_video(
                    reel_id=reel_id,
                    title=reel["title"],
                    summary=reel["summary"],
                    stock_video_path=stock_video_path,
                    sound_effect_path=sound_effect_path if os.path.exists(sound_effect_path) else None,
                    tts_audio_path=str(tts_path) if tts_path else None,
                    category=reel["category"],
                )
                print(f"  → Video saved: {video_path}")

                # Update reel with video path
                conn.execute(
                    "UPDATE reels SET video_path = ? WHERE id = ?",
                    (video_path, reel_id),
                )
                conn.commit()
            except Exception as e:
                print(f"  → Video composition failed: {e}")
                video_path = None

            print(f"  → Reel #{reel_id} created: {reel['title']}")
            continue

        # If no stock video, still insert the reel (text-only)
        tagged_keywords = f"{reel['keywords']}, {SEED_MARKER}"
        conn.execute(
            """INSERT INTO reels (upload_id, title, summary, narration, category, keywords)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (upload_id, reel["title"], reel["summary"], reel["narration"],
             reel["category"], tagged_keywords),
        )
        conn.commit()
        reel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        print(f"  → Reel #{reel_id} created (text-only): {reel['title']}")

    conn.close()
    print("\nDone! Video reels seeded successfully.")


if __name__ == "__main__":
    main()
