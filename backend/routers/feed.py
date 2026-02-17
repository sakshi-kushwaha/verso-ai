from fastapi import APIRouter, Query, Depends
from database import get_db
from auth import get_current_user

router = APIRouter()


@router.get("/feed")
def get_feed(page: int = Query(1, ge=1), limit: int = Query(5, ge=1, le=50),
             user: dict = Depends(get_current_user)):
    offset = (page - 1) * limit
    conn = get_db()

    reels = conn.execute(
        """SELECT r.* FROM reels r
           JOIN uploads u ON r.upload_id = u.id
           WHERE u.user_id = ?
           ORDER BY r.created_at DESC LIMIT ? OFFSET ?""",
        (user["id"], limit, offset),
    ).fetchall()

    total = conn.execute(
        """SELECT COUNT(*) FROM reels r
           JOIN uploads u ON r.upload_id = u.id
           WHERE u.user_id = ?""",
        (user["id"],),
    ).fetchone()[0]

    conn.close()

    return {
        "reels": [dict(r) for r in reels],
        "total": total,
        "page": page,
    }
