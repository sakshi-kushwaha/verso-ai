from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_db
from auth import hash_password, verify_password, create_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthBody(BaseModel):
    name: str
    password: str


@router.post("/signup")
def signup(body: AuthBody):
    name = body.name.strip()
    password = body.password.strip()
    if not name or not password:
        raise HTTPException(status_code=400, detail="Name and password required")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    conn = get_db()
    try:
        existing = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")

        hashed = hash_password(password)
        cursor = conn.execute(
            "INSERT INTO users (name, password_hash) VALUES (?, ?)",
            (name, hashed),
        )
        user_id = cursor.lastrowid
        conn.execute(
            "INSERT OR IGNORE INTO user_preferences (user_id, display_name, learning_style, content_depth, use_case, flashcard_difficulty) VALUES (?, ?, 'mixed', 'balanced', 'learning', 'medium')",
            (user_id, name),
        )
        conn.commit()
    finally:
        conn.close()

    token = create_token(user_id, name)
    return {"token": token, "user": {"id": user_id, "name": name}}


@router.post("/login")
def login(body: AuthBody):
    name = body.name.strip()
    password = body.password.strip()
    if not name or not password:
        raise HTTPException(status_code=400, detail="Name and password required")

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, name, password_hash FROM users WHERE name = ?", (name,)
        ).fetchone()
    finally:
        conn.close()

    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(row["id"], row["name"])
    return {"token": token, "user": {"id": row["id"], "name": row["name"]}}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, name, created_at FROM users WHERE id = ?", (user["id"],)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        uploads = conn.execute(
            "SELECT COUNT(*) FROM uploads WHERE user_id = ? AND status = 'done'", (user["id"],)
        ).fetchone()[0]
        reels = conn.execute(
            "SELECT COUNT(*) FROM reels r JOIN uploads u ON r.upload_id = u.id WHERE u.user_id = ?", (user["id"],)
        ).fetchone()[0]
        flashcards = conn.execute(
            "SELECT COUNT(*) FROM flashcards f JOIN uploads u ON f.upload_id = u.id WHERE u.user_id = ?", (user["id"],)
        ).fetchone()[0]
    finally:
        conn.close()

    return {**dict(row), "total_uploads": uploads, "total_reels": reels, "total_flashcards": flashcards}
