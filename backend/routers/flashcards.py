from fastapi import APIRouter, Query, Depends
from database import get_db
from auth import get_current_user

router = APIRouter()


@router.get("/flashcards")
def get_flashcards(upload_id: int = Query(None),
                   user: dict = Depends(get_current_user)):
    conn = get_db()

    if upload_id:
        rows = conn.execute(
            """SELECT f.* FROM flashcards f
               JOIN uploads u ON f.upload_id = u.id
               WHERE f.upload_id = ? AND u.user_id = ?
               ORDER BY f.created_at DESC""",
            (upload_id, user["id"]),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT f.* FROM flashcards f
               JOIN uploads u ON f.upload_id = u.id
               WHERE u.user_id = ?
               ORDER BY f.created_at DESC""",
            (user["id"],),
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]
