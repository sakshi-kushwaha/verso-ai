"""Backfill bg_image for existing reels that don't have one assigned."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import get_db
from bg_images import assign_images


def backfill():
    conn = get_db()

    # Get all reels without bg_image, grouped by upload_id
    rows = conn.execute(
        """SELECT r.id, r.category, r.upload_id
           FROM reels r
           WHERE r.bg_image IS NULL
           ORDER BY r.upload_id, r.id"""
    ).fetchall()

    if not rows:
        print("No reels to backfill.")
        conn.close()
        return

    # Group by upload_id
    uploads = {}
    for row in rows:
        uid = row["upload_id"]
        if uid not in uploads:
            uploads[uid] = []
        uploads[uid].append({"id": row["id"], "category": row["category"]})

    total = 0
    for upload_id, reels in uploads.items():
        # Get upload's subject_category
        upload_row = conn.execute(
            "SELECT subject_category FROM uploads WHERE id = ?", (upload_id,)
        ).fetchone()
        upload_cat = upload_row["subject_category"] if upload_row and upload_row["subject_category"] else "general"

        bg_paths = assign_images(reels, upload_cat)
        for reel, bg_path in zip(reels, bg_paths):
            if bg_path:
                conn.execute(
                    "UPDATE reels SET bg_image = ? WHERE id = ?",
                    (bg_path, reel["id"]),
                )
                total += 1

    conn.commit()
    conn.close()
    print(f"Backfilled {total} reels with background images.")


if __name__ == "__main__":
    backfill()
