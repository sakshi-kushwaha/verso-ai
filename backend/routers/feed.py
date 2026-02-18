from fastapi import APIRouter, Query, Depends
from database import get_db
from auth import get_current_user

router = APIRouter()


@router.get("/feed")
def get_feed(page: int = Query(1, ge=1), limit: int = Query(5, ge=1, le=50),
             upload_id: int = Query(None),
             tab: str = Query("all"),
             user: dict = Depends(get_current_user)):
    offset = (page - 1) * limit
    conn = get_db()

    if upload_id:
        reels = conn.execute(
            """SELECT r.* FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.user_id = ? AND r.upload_id = ?
               ORDER BY r.created_at DESC LIMIT ? OFFSET ?""",
            (user["id"], upload_id, limit, offset),
        ).fetchall()
        total = conn.execute(
            """SELECT COUNT(*) FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.user_id = ? AND r.upload_id = ?""",
            (user["id"], upload_id),
        ).fetchone()[0]
    elif tab == "explore":
        reels = conn.execute(
            """SELECT r.* FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.doc_type = 'seed'
               ORDER BY r.created_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        total = conn.execute(
            """SELECT COUNT(*) FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.doc_type = 'seed'""",
        ).fetchone()[0]
    elif tab == "my-docs":
        reels = conn.execute(
            """SELECT r.* FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.user_id = ? AND u.doc_type != 'seed'
               ORDER BY r.created_at DESC LIMIT ? OFFSET ?""",
            (user["id"], limit, offset),
        ).fetchall()
        total = conn.execute(
            """SELECT COUNT(*) FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.user_id = ? AND u.doc_type != 'seed'""",
            (user["id"],),
        ).fetchone()[0]
    else:
        reels = conn.execute(
            """SELECT r.* FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.user_id = ? OR u.doc_type = 'seed'
               ORDER BY r.created_at DESC LIMIT ? OFFSET ?""",
            (user["id"], limit, offset),
        ).fetchall()
        total = conn.execute(
            """SELECT COUNT(*) FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.user_id = ? OR u.doc_type = 'seed'""",
            (user["id"],),
        ).fetchone()[0]

    conn.close()

    return {
        "reels": [dict(r) for r in reels],
        "total": total,
        "page": page,
    }
