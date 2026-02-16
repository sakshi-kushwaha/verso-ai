from fastapi import APIRouter, Query
from database import get_db

router = APIRouter()


@router.get("/feed")
def get_feed(page: int = Query(1, ge=1), limit: int = Query(5, ge=1, le=50)):
    offset = (page - 1) * limit
    conn = get_db()

    reels = conn.execute(
        "SELECT * FROM reels ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM reels").fetchone()[0]
    conn.close()

    return {
        "reels": [dict(r) for r in reels],
        "total": total,
        "page": page,
    }
