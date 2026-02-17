from typing import Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_db
from auth import get_current_user

router = APIRouter(tags=["onboarding"])


class PreferencesBody(BaseModel):
    display_name: str = ""
    learning_style: Literal["visual", "auditory", "reading", "mixed"] = "reading"
    content_depth: Literal["brief", "balanced", "detailed"] = "balanced"
    use_case: Literal["exam", "work", "learning", "research"] = "learning"
    flashcard_difficulty: Literal["easy", "medium", "hard"] = "medium"


@router.put("/onboarding/preferences")
def upsert_preferences(body: PreferencesBody, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO user_preferences
                   (user_id, display_name, learning_style, content_depth, use_case, flashcard_difficulty, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET
                   display_name = excluded.display_name,
                   learning_style = excluded.learning_style,
                   content_depth = excluded.content_depth,
                   use_case = excluded.use_case,
                   flashcard_difficulty = excluded.flashcard_difficulty,
                   updated_at = datetime('now')""",
            (user_id, body.display_name, body.learning_style,
             body.content_depth, body.use_case, body.flashcard_difficulty),
        )
        conn.commit()
    finally:
        conn.close()
    return {"status": "saved", "user_id": user_id}


@router.get("/onboarding/preferences")
def get_preferences(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Preferences not found")
    return dict(row)


@router.get("/onboarding/status")
def get_status(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT display_name FROM user_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    completed = bool(row and row["display_name"])
    return {"completed": completed}
