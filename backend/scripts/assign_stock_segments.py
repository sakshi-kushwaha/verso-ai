#!/usr/bin/env python3
"""
Assign stock-video segments JSON to existing reels, and optionally recompose videos.

Usage:
  python -m backend.scripts.assign_stock_segments            # assign segments only
  python -m backend.scripts.assign_stock_segments --recompose # also compose videos
"""
from __future__ import annotations

import argparse
import json
import random
from typing import List, Dict, Set, DefaultDict
from collections import defaultdict
import os

# Support running as `python -m scripts.assign_stock_segments` (cwd=backend)
# and as `python -m backend.scripts.assign_stock_segments` (cwd=repo root)
try:
    from database import get_db, init_db  # type: ignore
    from video import load_video_catalog, get_clips_for_category  # type: ignore
    from config import VIDEO_CACHE_DIR  # type: ignore
    from bg_images import _resolve_category  # type: ignore
except ImportError:  # pragma: no cover
    from backend.database import get_db, init_db
    from backend.video import load_video_catalog, get_clips_for_category
    from backend.config import VIDEO_CACHE_DIR
    from backend.bg_images import _resolve_category


def _tokenize(text: str) -> List[str]:
    import re
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower())
    # collapse simple plurals
    norm = [w[:-1] if len(w) > 4 and w.endswith('s') else w for w in words]
    return norm


def _score_clip(clip: Dict, kwset: set[str]) -> float:
    desc = (clip.get("description") or "").lower()
    file = (clip.get("file") or "").lower()
    text = f"{desc} {file}"
    score = 0.0
    for kw in kwset:
        if kw in text:
            # weight by keyword specificity (length)
            score += 1.0 + min(len(kw) / 6.0, 1.0)
    return score


def pick_segments_for_reel(title: str, summary: str, narration: str, keywords: str,
                            reel_category: str, upload_category: str,
                            total_duration: float = 15.0, n_segments: int = 4,
                            avoid_files: Set[str] | None = None) -> List[Dict]:
    """Pick relevant clips by scoring catalog descriptions against reel text/keywords."""
    # Resolve category to catalog slug (science, law, etc.)
    cat = _resolve_category(reel_category or "", upload_category or "general")
    base = get_clips_for_category(cat) or []
    # also include some "general" clips as fallback options
    catalog = load_video_catalog() or {}
    base += catalog.get("general", [])
    if not base:
        # last resort: flatten any available clips
        for _, items in catalog.items():
            base.extend(items)
    # Build keyword set from content
    text = " ".join([title or "", summary or "", narration or "", keywords or ""]).lower()
    toks = set(_tokenize(text))
    # prune overly common words
    stop = {
        "the","and","with","from","into","about","over","under","this","that","these","those",
        "study","topic","chapter","section","introduction","conclusion","concept","example","important",
        "learn","learning","explain","explained","include","including","general","overview",
    }
    kwset = {w for w in toks if len(w) >= 4 and w not in stop}

    # Score and pick top-N distinct files
    scored = []
    seen = set()
    for c in base:
        f = c.get("file")
        if not f or f in seen:
            continue
        seen.add(f)
        scored.append(( _score_clip(c, kwset), c))

    scored.sort(key=lambda x: x[0], reverse=True)
    # Prefer high-score clips while avoiding already-used files for this upload
    chosen: List[Dict] = []
    avoid = set(avoid_files or set())
    for s, c in scored:
        if len(chosen) >= max(2, n_segments):
            break
        if c.get("file") in avoid:
            continue
        if s <= 0 and chosen:
            break
        chosen.append(c)
        avoid.add(c.get("file"))
    # If too few selected, fill with random unseen options
    if len(chosen) < 2:
        random.shuffle(base)
        for c in base:
            f = c.get("file")
            if c not in chosen and f not in avoid:
                chosen.append(c)
            if len(chosen) >= max(2, n_segments):
                break

    # Assign durations roughly evenly (>=2s each) and normalize to total_duration
    base_dur = max(2.0, total_duration / len(chosen))
    durations = [base_dur for _ in chosen]
    s = sum(durations)
    if s > 0:
        scale = total_duration / s
        durations = [round(max(2.0, d * scale), 2) for d in durations]
    drift = round(total_duration - sum(durations), 2)
    if abs(drift) >= 0.01 and durations:
        durations[0] = round(max(2.0, durations[0] + drift), 2)

    return [{"type": "video", "clip": c["file"], "duration": float(d)} for c, d in zip(chosen, durations)]


def assign_segments(recompose: bool = False, force: bool = False) -> None:
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT r.id AS reel_id, r.upload_id, r.title, r.summary, r.narration, r.category,
                   r.keywords, u.subject_category, r.segments_json
            FROM reels r
            JOIN uploads u ON r.upload_id = u.id
            WHERE ? = 1 OR r.segments_json IS NULL OR r.segments_json = ''
            ORDER BY r.id
            """,
            (1 if force else 0,),
        ).fetchall()

        if not rows:
            print("No reels need segments. Done.")
            return

        print(f"Assigning segments for {len(rows)} reels...")

        # Group reels by upload so we can avoid repeating clips within the same PDF
        by_upload: DefaultDict[int, list] = defaultdict(list)
        for r in rows:
            by_upload[r["upload_id"]].append(r)

        for upload_id, items in by_upload.items():
            # Build set of already-used clips in this upload (from existing segments of other reels)
            used: Set[str] = set()
            if not force:
                exist = conn.execute(
                    "SELECT segments_json FROM reels WHERE upload_id = ?",
                    (upload_id,)
                ).fetchall()
                for e in exist:
                    try:
                        data = json.loads(e[0]) if e and e[0] else None
                        segs = data.get("segments", data) if isinstance(data, (dict, list)) else []
                        if isinstance(segs, dict):
                            segs = segs.get("segments", [])
                        for seg in (segs or []):
                            f = (seg or {}).get("clip")
                            if f:
                                used.add(f)
                    except Exception:
                        pass

            for row in items:
                segs = pick_segments_for_reel(
                    title=row["title"], summary=row["summary"], narration=row["narration"],
                    keywords=row["keywords"] if "keywords" in row.keys() else "",
                    reel_category=row["category"], upload_category=row["subject_category"],
                    avoid_files=used,
                )
                # Update used set so later reels from the same upload avoid repeats
                for seg in segs:
                    if seg.get("clip"):
                        used.add(seg["clip"])

                payload = json.dumps({"segments": segs})
                conn.execute("UPDATE reels SET segments_json = ? WHERE id = ?", (payload, row["reel_id"]))
        conn.commit()

    finally:
        conn.close()

    if recompose:
        # Compose videos using the assigned segments
        from pipeline import _try_compose_video_with_segments
        from database import get_db as _get_db

        c2 = _get_db()
        try:
            to_compose = c2.execute(
                """
                SELECT r.id AS reel_id, r.upload_id, r.title, r.summary, r.narration, r.category,
                       u.subject_category, r.segments_json, r.video_path
                FROM reels r
                JOIN uploads u ON r.upload_id = u.id
                WHERE r.segments_json IS NOT NULL AND (? = 1 OR r.video_path IS NULL OR r.video_path = '')
                ORDER BY r.id
                """,
                (1 if force else 0,),
            ).fetchall()

            for row in to_compose:
                segs = []
                try:
                    data = json.loads(row["segments_json"]) if row["segments_json"] else None
                    if isinstance(data, dict) and "segments" in data:
                        segs = data["segments"]
                    elif isinstance(data, list):
                        segs = data
                except Exception:
                    segs = []

                # Force recompose: delete cached file if present so composer rebuilds it
                if force:
                    try:
                        cache_path = os.path.join(str(VIDEO_CACHE_DIR), f"reel_{row['reel_id']}.mp4")
                        if os.path.exists(cache_path):
                            os.remove(cache_path)
                    except Exception:
                        pass

                reel_obj = {
                    "title": row["title"],
                    "summary": row["summary"],
                    "narration": row["narration"],
                    "category": row["category"],
                }
                _try_compose_video_with_segments(row["reel_id"], reel_obj, row["subject_category"], segs)
        finally:
            c2.close()


def main() -> None:
    # Ensure DB migrations ran (adds segments_json column if missing)
    init_db()
    parser = argparse.ArgumentParser(description="Assign stock-video segments JSON to reels")
    parser.add_argument("--recompose", action="store_true", help="Compose videos after assigning segments")
    parser.add_argument("--force", action="store_true", help="Reassign segments and recompose even if video exists")
    args = parser.parse_args()
    assign_segments(recompose=args.recompose, force=args.force)


if __name__ == "__main__":
    main()
