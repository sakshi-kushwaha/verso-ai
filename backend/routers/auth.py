from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from database import get_db
from auth import (
    hash_password,
    verify_password,
    validate_password,
    create_token,
    get_current_user,
    create_refresh_token,
    rotate_refresh_token,
    revoke_user_sessions,
    verify_refresh_token,
    _hash_refresh_token,
)
from rate_limit import login_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthBody(BaseModel):
    name: str
    password: str
    remember_me: bool = False


class RefreshBody(BaseModel):
    refresh_token: str


class LogoutBody(BaseModel):
    refresh_token: Optional[str] = None


# ── Signup ──────────────────────────────────────────────────

@router.post("/signup")
def signup(body: AuthBody, request: Request):
    name = body.name.strip()
    password = body.password.strip()
    if not name or not password:
        raise HTTPException(status_code=400, detail="Name and password required")

    ok, msg = validate_password(password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

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

    device_info = request.headers.get("User-Agent", "")
    ip = request.client.host if request.client else ""
    token = create_token(user_id, name)
    refresh = create_refresh_token(user_id, name, device_info, ip, body.remember_me)
    return {"token": token, "refresh_token": refresh, "user": {"id": user_id, "name": name}}


# ── Login ───────────────────────────────────────────────────

@router.post("/login")
def login(body: AuthBody, request: Request):
    name = body.name.strip()
    password = body.password.strip()
    if not name or not password:
        raise HTTPException(status_code=400, detail="Name and password required")

    ip = request.client.host if request.client else "unknown"
    rate_key = f"{ip}:{name}"

    # Rate limiting (per IP+username)
    if login_limiter.is_limited(rate_key):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please wait and try again.",
        )

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, name, password_hash, failed_login_attempts, locked_until FROM users WHERE name = ?",
            (name,),
        ).fetchone()

        if not row:
            login_limiter.record(rate_key)
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Account lockout check
        if row["locked_until"]:
            locked = datetime.fromisoformat(row["locked_until"])
            now = datetime.now(timezone.utc)
            # DB stores naive UTC datetimes
            locked_utc = locked.replace(tzinfo=timezone.utc) if locked.tzinfo is None else locked
            if now < locked_utc:
                remaining = int((locked_utc - now).total_seconds() / 60) + 1
                raise HTTPException(
                    status_code=429,
                    detail=f"Account locked due to too many failed attempts. Try again in {remaining} minute(s).",
                )

        # Verify password
        if not verify_password(password, row["password_hash"]):
            login_limiter.record(rate_key)
            attempts = (row["failed_login_attempts"] or 0) + 1
            if attempts >= 5:
                conn.execute(
                    "UPDATE users SET failed_login_attempts = ?, locked_until = datetime('now', '+15 minutes') WHERE id = ?",
                    (attempts, row["id"]),
                )
            else:
                conn.execute(
                    "UPDATE users SET failed_login_attempts = ? WHERE id = ?",
                    (attempts, row["id"]),
                )
            conn.commit()
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # Success — reset lockout counters
        conn.execute(
            "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
            (row["id"],),
        )
        conn.commit()
    finally:
        conn.close()

    device_info = request.headers.get("User-Agent", "")
    token = create_token(row["id"], row["name"])
    refresh = create_refresh_token(row["id"], row["name"], device_info, ip, body.remember_me)
    return {"token": token, "refresh_token": refresh, "user": {"id": row["id"], "name": row["name"]}}


# ── Refresh ─────────────────────────────────────────────────

@router.post("/refresh")
def refresh(body: RefreshBody, request: Request):
    device_info = request.headers.get("User-Agent", "")
    ip = request.client.host if request.client else ""
    result = rotate_refresh_token(body.refresh_token, device_info, ip)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access, new_refresh = result
    return {"token": access, "refresh_token": new_refresh}


# ── Logout ──────────────────────────────────────────────────

@router.post("/logout")
def logout(body: LogoutBody):
    if body.refresh_token:
        token_hash = _hash_refresh_token(body.refresh_token)
        conn = get_db()
        try:
            conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = ?",
                (token_hash,),
            )
            conn.commit()
        finally:
            conn.close()
    return {"ok": True}


# ── Me ──────────────────────────────────────────────────────

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


# ── Sessions ────────────────────────────────────────────────

@router.get("/sessions")
def list_sessions(request: Request, user: dict = Depends(get_current_user)):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, device_info, ip_address, created_at FROM refresh_tokens "
            "WHERE user_id = ? AND revoked = 0 AND expires_at > datetime('now') "
            "ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r["id"],
            "device_info": r["device_info"],
            "ip_address": r["ip_address"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: int, user: dict = Depends(get_current_user)):
    conn = get_db()
    try:
        result = conn.execute(
            "UPDATE refresh_tokens SET revoked = 1 WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Session not found")
    finally:
        conn.close()
    return {"ok": True}


@router.post("/sessions/revoke-all")
def revoke_all_sessions(body: RefreshBody, user: dict = Depends(get_current_user)):
    """Revoke all sessions except the current one."""
    current_hash = _hash_refresh_token(body.refresh_token)
    revoke_user_sessions(user["id"], except_token_hash=current_hash)
    return {"ok": True}


# ── Profile editing ─────────────────────────────────────────

class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


@router.put("/profile")
def update_profile(body: ProfileUpdate, user: dict = Depends(get_current_user)):
    conn = get_db()
    try:
        if body.new_password:
            if not body.current_password:
                raise HTTPException(status_code=400, detail="Current password required to change password")
            row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
            if not verify_password(body.current_password, row["password_hash"]):
                raise HTTPException(status_code=401, detail="Current password is incorrect")
            ok, msg = validate_password(body.new_password)
            if not ok:
                raise HTTPException(status_code=400, detail=msg)
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(body.new_password), user["id"]),
            )

        if body.display_name is not None:
            conn.execute(
                "UPDATE user_preferences SET display_name = ?, updated_at = datetime('now') WHERE user_id = ?",
                (body.display_name.strip(), user["id"]),
            )

        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


# ── Account deletion ────────────────────────────────────────

class DeleteAccountBody(BaseModel):
    password: str


@router.delete("/account")
def delete_account(body: DeleteAccountBody, user: dict = Depends(get_current_user)):
    conn = get_db()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not verify_password(body.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Incorrect password")

        uid = user["id"]
        # Delete user data (order: dependents first)
        conn.execute("DELETE FROM refresh_tokens WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM security_questions WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM reel_interactions WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM reel_likes WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM bookmarks WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM progress WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM user_preferences WHERE user_id = ?", (uid,))
        # Delete uploads and their dependent data
        upload_ids = [r[0] for r in conn.execute("SELECT id FROM uploads WHERE user_id = ?", (uid,)).fetchall()]
        if upload_ids:
            placeholders = ",".join("?" * len(upload_ids))
            conn.execute(f"DELETE FROM reels WHERE upload_id IN ({placeholders})", upload_ids)
            conn.execute(f"DELETE FROM flashcards WHERE upload_id IN ({placeholders})", upload_ids)
            conn.execute(f"DELETE FROM chat_history WHERE upload_id IN ({placeholders})", upload_ids)
            conn.execute(f"DELETE FROM chat_summaries WHERE upload_id IN ({placeholders})", upload_ids)
            conn.execute(f"DELETE FROM uploads WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


# ── Security questions ──────────────────────────────────────

PREDEFINED_QUESTIONS = [
    "What is the name of your first pet?",
    "What city were you born in?",
    "What was the name of your first school?",
    "What is your mother's maiden name?",
    "What was the make of your first car?",
    "What is the name of your favorite childhood friend?",
    "What street did you grow up on?",
    "What is your favorite book?",
]


class SecurityQuestionItem(BaseModel):
    question: str
    answer: str


class SetSecurityQuestions(BaseModel):
    questions: list[SecurityQuestionItem]


@router.post("/security-questions")
def set_security_questions(body: SetSecurityQuestions, user: dict = Depends(get_current_user)):
    if len(body.questions) < 2:
        raise HTTPException(status_code=400, detail="At least 2 security questions required")
    if len(body.questions) > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 security questions allowed")

    conn = get_db()
    try:
        conn.execute("DELETE FROM security_questions WHERE user_id = ?", (user["id"],))
        for q in body.questions:
            answer = q.answer.strip().lower()
            if not answer:
                raise HTTPException(status_code=400, detail="Answers cannot be empty")
            conn.execute(
                "INSERT INTO security_questions (user_id, question, answer_hash) VALUES (?, ?, ?)",
                (user["id"], q.question, hash_password(answer)),
            )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.get("/security-questions")
def get_security_questions(user: dict = Depends(get_current_user)):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, question FROM security_questions WHERE user_id = ?",
            (user["id"],),
        ).fetchall()
    finally:
        conn.close()
    return {"questions": [{"id": r["id"], "question": r["question"]} for r in rows]}


@router.get("/security-questions/predefined")
def get_predefined_questions():
    return {"questions": PREDEFINED_QUESTIONS}


# ── Forgot password ─────────────────────────────────────────

class ForgotPasswordLookup(BaseModel):
    username: str


@router.post("/forgot-password/questions")
def forgot_password_questions(body: ForgotPasswordLookup, request: Request):
    """Return security questions for a user (unauthenticated)."""
    ip = request.client.host if request.client else "unknown"
    rate_key = f"forgot:{ip}"
    if login_limiter.is_limited(rate_key):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait and try again.")
    login_limiter.record(rate_key)

    conn = get_db()
    try:
        user = conn.execute("SELECT id FROM users WHERE name = ?", (body.username.strip(),)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        rows = conn.execute(
            "SELECT id, question FROM security_questions WHERE user_id = ?",
            (user["id"],),
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=400, detail="No security questions set for this account")
    finally:
        conn.close()
    return {"questions": [{"id": r["id"], "question": r["question"]} for r in rows]}


class VerifyAnswersBody(BaseModel):
    username: str
    answers: list[dict]  # [{"question_id": int, "answer": str}]


@router.post("/forgot-password/verify")
def forgot_password_verify(body: VerifyAnswersBody, request: Request):
    """Verify security question answers, return a reset token."""
    import time as _time
    ip = request.client.host if request.client else "unknown"
    rate_key = f"reset:{ip}:{body.username}"
    if login_limiter.is_limited(rate_key):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait and try again.")
    login_limiter.record(rate_key)

    conn = get_db()
    try:
        user = conn.execute("SELECT id, name FROM users WHERE name = ?", (body.username.strip(),)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        for ans in body.answers:
            row = conn.execute(
                "SELECT answer_hash FROM security_questions WHERE id = ? AND user_id = ?",
                (ans["question_id"], user["id"]),
            ).fetchone()
            if not row or not verify_password(ans["answer"].strip().lower(), row["answer_hash"]):
                raise HTTPException(status_code=401, detail="One or more answers are incorrect")
    finally:
        conn.close()

    # Issue a short-lived reset token (10 minutes)
    import jwt as _jwt
    reset_token = _jwt.encode(
        {"sub": user["id"], "name": user["name"], "purpose": "reset", "exp": int(_time.time()) + 600},
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"reset_token": reset_token}


class ResetPasswordBody(BaseModel):
    reset_token: str
    new_password: str


@router.post("/forgot-password/reset")
def forgot_password_reset(body: ResetPasswordBody):
    """Reset password using a valid reset token."""
    import jwt as _jwt
    try:
        payload = _jwt.decode(body.reset_token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("purpose") != "reset":
            raise HTTPException(status_code=401, detail="Invalid reset token")
    except _jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Reset token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid reset token")

    ok, msg = validate_password(body.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    user_id = payload["sub"]
    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET password_hash = ?, failed_login_attempts = 0, locked_until = NULL WHERE id = ?",
            (hash_password(body.new_password), user_id),
        )
        conn.execute("UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


# Import JWT_SECRET for reset token generation
from config import JWT_SECRET
