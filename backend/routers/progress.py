import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from database import get_db
from auth import get_current_user

router = APIRouter()


class ViewRecord(BaseModel):
    upload_id: int
    reel_id: int


@router.post("/progress/view")
def record_view(body: ViewRecord, user: dict = Depends(get_current_user)):
    conn = get_db()
    row = conn.execute(
        "SELECT viewed_reel_ids FROM progress WHERE user_id = ? AND upload_id = ?",
        (user["id"], body.upload_id),
    ).fetchone()

    if row:
        viewed = json.loads(row["viewed_reel_ids"])
        if body.reel_id not in viewed:
            viewed.append(body.reel_id)
        conn.execute(
            "UPDATE progress SET viewed_reel_ids = ?, last_viewed_at = datetime('now') WHERE user_id = ? AND upload_id = ?",
            (json.dumps(viewed), user["id"], body.upload_id),
        )
    else:
        conn.execute(
            "INSERT INTO progress (user_id, upload_id, viewed_reel_ids) VALUES (?, ?, ?)",
            (user["id"], body.upload_id, json.dumps([body.reel_id])),
        )

    conn.commit()
    conn.close()
    return {"message": "View recorded"}


@router.get("/progress/{upload_id}")
def get_progress(upload_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    row = conn.execute(
        "SELECT viewed_reel_ids, last_viewed_at FROM progress WHERE user_id = ? AND upload_id = ?",
        (user["id"], upload_id),
    ).fetchone()

    total_reels = conn.execute(
        "SELECT COUNT(*) FROM reels WHERE upload_id = ?", (upload_id,)
    ).fetchone()[0]

    conn.close()

    viewed = json.loads(row["viewed_reel_ids"]) if row else []
    return {
        "upload_id": upload_id,
        "viewed_reel_ids": viewed,
        "viewed_count": len(viewed),
        "total_reels": total_reels,
        "percent": round((len(viewed) / total_reels * 100) if total_reels > 0 else 0),
        "last_viewed_at": row["last_viewed_at"] if row else None,
    }


@router.get("/progress")
def get_all_progress(user: dict = Depends(get_current_user)):
    conn = get_db()

    uploads = conn.execute(
        """SELECT u.id, u.filename, u.doc_type,
                  (SELECT COUNT(*) FROM reels WHERE upload_id = u.id) AS total_reels,
                  (SELECT COUNT(*) FROM flashcards WHERE upload_id = u.id) AS total_flashcards
           FROM uploads u WHERE u.user_id = ? AND u.status = 'done'
           ORDER BY u.created_at DESC""",
        (user["id"],),
    ).fetchall()

    progress_rows = conn.execute(
        "SELECT upload_id, viewed_reel_ids, last_viewed_at FROM progress WHERE user_id = ?",
        (user["id"],),
    ).fetchall()

    chat_counts = conn.execute(
        """SELECT upload_id, COUNT(*) as count FROM chat_history
           WHERE upload_id IN (SELECT id FROM uploads WHERE user_id = ?)
           GROUP BY upload_id""",
        (user["id"],),
    ).fetchall()

    conn.close()

    progress_map = {r["upload_id"]: r for r in progress_rows}
    chat_map = {r["upload_id"]: r["count"] for r in chat_counts}

    results = []
    total_reels_viewed = 0
    total_reels = 0
    total_flashcards = 0
    total_chats = 0

    for u in uploads:
        uid = u["id"]
        p = progress_map.get(uid)
        viewed = json.loads(p["viewed_reel_ids"]) if p else []
        tr = u["total_reels"]
        chats = chat_map.get(uid, 0)

        total_reels_viewed += len(viewed)
        total_reels += tr
        total_flashcards += u["total_flashcards"]
        total_chats += chats

        results.append({
            "upload_id": uid,
            "filename": u["filename"],
            "doc_type": u["doc_type"],
            "viewed_count": len(viewed),
            "total_reels": tr,
            "percent": round((len(viewed) / tr * 100) if tr > 0 else 0),
            "chat_count": chats,
            "last_viewed_at": p["last_viewed_at"] if p else None,
        })

    overall = round((total_reels_viewed / total_reels * 100) if total_reels > 0 else 0)

    return {
        "overall_percent": overall,
        "total_reels_viewed": total_reels_viewed,
        "total_reels": total_reels,
        "total_flashcards": total_flashcards,
        "total_chats": total_chats,
        "uploads": results,
    }
