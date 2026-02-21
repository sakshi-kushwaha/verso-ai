"""Feed ranking algorithm — scores reels based on user interaction history.

Signals tracked: view (with time), like, bookmark, skip.
Cold start: all categories score 0.5 (neutral), feed degrades to recency + jitter.
"""
from datetime import datetime
import random

# --- Weights for the final score ---
W_CATEGORY = 0.40
W_NOVELTY = 0.25
W_RECENCY = 0.15
W_POPULARITY = 0.10
W_SEEN_PENALTY = 0.10

# --- Thresholds ---
SKIP_THRESHOLD_MS = 2000
ENGAGED_VIEW_MS = 5000
HALF_LIFE_HOURS = 168  # 7 days


def build_user_profile(conn, user_id: int) -> dict:
    """Aggregate interaction history into a user preference profile."""

    # Category affinity scores from interactions
    rows = conn.execute(
        """SELECT r.category,
                  SUM(CASE WHEN i.action = 'like' THEN 3.0
                           WHEN i.action = 'bookmark' THEN 2.0
                           WHEN i.action = 'view' AND i.time_spent_ms > 5000 THEN 1.0
                           WHEN i.action = 'view' AND i.time_spent_ms BETWEEN 2000 AND 5000 THEN 0.5
                           WHEN i.action = 'skip' THEN -1.5
                           ELSE 0 END) AS score
           FROM reel_interactions i
           JOIN reels r ON i.reel_id = r.id
           WHERE i.user_id = ?
           GROUP BY r.category""",
        (user_id,),
    ).fetchall()

    category_scores = {}
    for row in rows:
        cat = row["category"] or "General"
        category_scores[cat] = row["score"] or 0

    # Normalize to [0, 1]
    if category_scores:
        max_score = max(category_scores.values())
        min_score = min(category_scores.values())
        spread = max_score - min_score
        if spread > 0:
            category_scores = {
                cat: (score - min_score) / spread
                for cat, score in category_scores.items()
            }
        else:
            category_scores = {cat: 0.5 for cat in category_scores}

    # Sets for quick lookup
    liked = set()
    bookmarked = set()
    viewed = set()
    skipped = set()

    interaction_rows = conn.execute(
        "SELECT reel_id, action FROM reel_interactions WHERE user_id = ?",
        (user_id,),
    ).fetchall()

    total_interactions = len(interaction_rows)
    for row in interaction_rows:
        rid = row["reel_id"]
        act = row["action"]
        if act == "like":
            liked.add(rid)
        elif act == "unlike":
            liked.discard(rid)
        elif act == "bookmark":
            bookmarked.add(rid)
        elif act == "unbookmark":
            bookmarked.discard(rid)
        elif act == "view":
            viewed.add(rid)
        elif act == "skip":
            skipped.add(rid)

    return {
        "category_scores": category_scores,
        "liked_reel_ids": liked,
        "bookmarked_reel_ids": bookmarked,
        "viewed_reel_ids": viewed,
        "skipped_reel_ids": skipped,
        "total_interactions": total_interactions,
    }


def compute_popularity(conn, reel_ids: list) -> dict:
    """Return {reel_id: normalized_popularity} based on global likes + bookmarks."""
    if not reel_ids:
        return {}

    placeholders = ",".join("?" for _ in reel_ids)
    rows = conn.execute(
        f"""SELECT reel_id, COUNT(*) AS cnt
            FROM reel_interactions
            WHERE reel_id IN ({placeholders}) AND action IN ('like', 'bookmark')
            GROUP BY reel_id""",
        reel_ids,
    ).fetchall()

    pop = {rid: 0 for rid in reel_ids}
    for row in rows:
        pop[row["reel_id"]] = row["cnt"]

    max_pop = max(pop.values()) if pop else 0
    if max_pop > 0:
        return {rid: cnt / max_pop for rid, cnt in pop.items()}
    return {rid: 0.0 for rid in reel_ids}


def _parse_datetime(dt_str: str) -> datetime:
    """Parse SQLite datetime string."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(dt_str, fmt)
        except (ValueError, TypeError):
            continue
    return datetime.utcnow()


def score_reel(reel: dict, profile: dict, popularity: dict, now: datetime) -> float:
    """Score a single reel for a user. Returns float roughly in [0, 1]."""
    reel_id = reel["id"]
    category = reel.get("category") or "General"

    # 1. Category affinity
    if profile["total_interactions"] == 0:
        category_affinity = 0.5  # neutral for cold start
    else:
        category_affinity = profile["category_scores"].get(category, 0.5)

    # 2. Novelty — unseen content boosted
    novelty = 0.0 if reel_id in profile["viewed_reel_ids"] else 1.0

    # 3. Recency — time decay with 7-day half-life
    created_at = _parse_datetime(reel.get("created_at", ""))
    age_hours = max((now - created_at).total_seconds() / 3600, 0)
    recency = 2 ** (-age_hours / HALF_LIFE_HOURS)

    # 4. Popularity — global signal
    pop = popularity.get(reel_id, 0.0)

    # 5. Seen penalty — demote viewed content (but not if liked/bookmarked)
    is_favorited = reel_id in profile["liked_reel_ids"] or reel_id in profile["bookmarked_reel_ids"]
    seen_penalty = 0.0
    if reel_id in profile["viewed_reel_ids"] and not is_favorited:
        seen_penalty = 1.0

    score = (
        W_CATEGORY * category_affinity
        + W_NOVELTY * novelty
        + W_RECENCY * recency
        + W_POPULARITY * pop
        - W_SEEN_PENALTY * seen_penalty
    )

    # Small jitter to break ties and add variety
    score += random.uniform(0, 0.03)

    return score


def rank_feed(conn, user_id: int, candidate_reels: list, page: int = 1, limit: int = 5) -> list:
    """Score and rank candidate reels for a user, return the requested page."""
    if not candidate_reels:
        return []

    profile = build_user_profile(conn, user_id)
    reel_ids = [r["id"] for r in candidate_reels]
    popularity = compute_popularity(conn, reel_ids)
    now = datetime.utcnow()

    scored = []
    for reel in candidate_reels:
        s = score_reel(reel, profile, popularity, now)
        scored.append((s, reel))

    scored.sort(key=lambda x: x[0], reverse=True)

    start = (page - 1) * limit
    end = start + limit
    return [reel for _, reel in scored[start:end]]
