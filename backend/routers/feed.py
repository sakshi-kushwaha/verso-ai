from fastapi import APIRouter, Query, Depends
from database import get_db
from auth import get_current_user
from algorithm import rank_feed

router = APIRouter()


@router.get("/feed")
def get_feed(page: int = Query(1, ge=1), limit: int = Query(5, ge=1, le=50),
             upload_id: int = Query(None),
             tab: str = Query("all"),
             user: dict = Depends(get_current_user)):
    offset = (page - 1) * limit
    conn = get_db()

    if upload_id:
        # Specific upload — chronological (user is reading a document sequentially)
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
        conn.close()
        return {"reels": [dict(r) for r in reels], "total": total, "page": page}

    if tab == "my-docs":
        # User's own docs — chronological
        reels = conn.execute(
            """SELECT r.* FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.user_id = ? AND u.doc_type != 'seed' AND u.filename != '__gold_standard__'
               ORDER BY r.created_at DESC LIMIT ? OFFSET ?""",
            (user["id"], limit, offset),
        ).fetchall()
        total = conn.execute(
            """SELECT COUNT(*) FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.user_id = ? AND u.doc_type != 'seed' AND u.filename != '__gold_standard__'""",
            (user["id"],),
        ).fetchone()[0]
        conn.close()
        return {"reels": [dict(r) for r in reels], "total": total, "page": page}

    # --- Algorithm-ranked tabs: "all" and "explore" ---
    if tab == "explore":
        reels = conn.execute(
            """SELECT r.* FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.doc_type = 'seed' OR u.filename = '__gold_standard__'""",
        ).fetchall()
    else:  # "all" (For You) — only user's own uploaded reels
        reels = conn.execute(
            """SELECT r.* FROM reels r
               JOIN uploads u ON r.upload_id = u.id
               WHERE u.user_id = ? AND u.doc_type != 'seed' AND u.filename != '__gold_standard__'""",
            (user["id"],),
        ).fetchall()

    candidates = [dict(r) for r in reels]
    total = len(candidates)
    ranked = rank_feed(conn, user["id"], candidates, page=page, limit=limit)

    conn.close()
    return {"reels": ranked, "total": total, "page": page}
