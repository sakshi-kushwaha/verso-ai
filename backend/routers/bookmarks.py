from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_db
from auth import get_current_user

router = APIRouter()


class BookmarkCreate(BaseModel):
    reel_id: Optional[int] = None
    flashcard_id: Optional[int] = None


@router.post("/bookmarks")
def add_bookmark(body: BookmarkCreate, user: dict = Depends(get_current_user)):
    if not body.reel_id and not body.flashcard_id:
        raise HTTPException(400, "Must provide reel_id or flashcard_id")

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM bookmarks WHERE user_id = ? AND reel_id IS ? AND flashcard_id IS ?",
        (user["id"], body.reel_id, body.flashcard_id),
    ).fetchone()
    if existing:
        conn.close()
        return {"id": existing["id"], "message": "Already bookmarked"}

    cursor = conn.execute(
        "INSERT INTO bookmarks (user_id, reel_id, flashcard_id) VALUES (?, ?, ?)",
        (user["id"], body.reel_id, body.flashcard_id),
    )
    bookmark_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": bookmark_id, "message": "Bookmarked"}


@router.delete("/bookmarks/{bookmark_id}")
def remove_bookmark(bookmark_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    result = conn.execute(
        "DELETE FROM bookmarks WHERE id = ? AND user_id = ?",
        (bookmark_id, user["id"]),
    )
    conn.commit()
    deleted = result.rowcount
    conn.close()
    if not deleted:
        raise HTTPException(404, "Bookmark not found")
    return {"message": "Bookmark removed"}


@router.get("/bookmarks")
def list_bookmarks(user: dict = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        """SELECT b.id, b.reel_id, b.flashcard_id, b.created_at,
                  r.title AS reel_title, r.summary AS reel_summary, r.category AS reel_category,
                  r.keywords AS reel_keywords, r.page_ref AS reel_page_ref,
                  f.question AS fc_question, f.answer AS fc_answer
           FROM bookmarks b
           LEFT JOIN reels r ON b.reel_id = r.id
           LEFT JOIN flashcards f ON b.flashcard_id = f.id
           WHERE b.user_id = ?
           ORDER BY b.created_at DESC""",
        (user["id"],),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
