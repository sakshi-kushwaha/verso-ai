from fastapi import APIRouter, Query
from database import get_db

router = APIRouter()


@router.get("/flashcards")
def get_flashcards(upload_id: int = Query(None)):
    conn = get_db()

    if upload_id:
        rows = conn.execute(
            "SELECT * FROM flashcards WHERE upload_id = ? ORDER BY created_at DESC",
            (upload_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM flashcards ORDER BY created_at DESC"
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]
