from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from auth import get_current_user

router = APIRouter()

VALID_ACTIONS = {"view", "like", "unlike", "skip", "bookmark", "unbookmark"}


class InteractionEvent(BaseModel):
    reel_id: int
    action: str
    time_spent_ms: Optional[int] = 0


@router.post("/interactions/track")
def track_interaction(body: InteractionEvent, user: dict = Depends(get_current_user)):
    if body.action not in VALID_ACTIONS:
        raise HTTPException(400, f"Invalid action. Must be one of: {VALID_ACTIONS}")

    conn = get_db()

    conn.execute(
        "INSERT INTO reel_interactions (user_id, reel_id, action, time_spent_ms) VALUES (?, ?, ?, ?)",
        (user["id"], body.reel_id, body.action, body.time_spent_ms or 0),
    )

    # Maintain reel_likes materialized state
    if body.action == "like":
        conn.execute(
            "INSERT OR IGNORE INTO reel_likes (user_id, reel_id) VALUES (?, ?)",
            (user["id"], body.reel_id),
        )
    elif body.action == "unlike":
        conn.execute(
            "DELETE FROM reel_likes WHERE user_id = ? AND reel_id = ?",
            (user["id"], body.reel_id),
        )

    conn.commit()
    conn.close()
    return {"status": "ok"}


@router.post("/interactions/batch")
def track_batch(events: List[InteractionEvent], user: dict = Depends(get_current_user)):
    conn = get_db()
    for e in events:
        if e.action not in VALID_ACTIONS:
            continue
        conn.execute(
            "INSERT INTO reel_interactions (user_id, reel_id, action, time_spent_ms) VALUES (?, ?, ?, ?)",
            (user["id"], e.reel_id, e.action, e.time_spent_ms or 0),
        )
        if e.action == "like":
            conn.execute(
                "INSERT OR IGNORE INTO reel_likes (user_id, reel_id) VALUES (?, ?)",
                (user["id"], e.reel_id),
            )
        elif e.action == "unlike":
            conn.execute(
                "DELETE FROM reel_likes WHERE user_id = ? AND reel_id = ?",
                (user["id"], e.reel_id),
            )
    conn.commit()
    conn.close()
    return {"status": "ok", "count": len(events)}


@router.get("/interactions/likes")
def get_user_likes(user: dict = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT reel_id FROM reel_likes WHERE user_id = ?",
        (user["id"],),
    ).fetchall()
    conn.close()
    return {"liked_reel_ids": [r["reel_id"] for r in rows]}
