import os
import re
import time
import hashlib
import secrets
import bcrypt
import jwt
from fastapi import Request, HTTPException
from config import JWT_SECRET
from database import get_db

SECRET_KEY = JWT_SECRET
ALGORITHM = "HS256"
TOKEN_EXPIRY = 30 * 60  # 30 minutes (access token)
REFRESH_TOKEN_EXPIRY = 7 * 24 * 3600  # 7 days
REFRESH_TOKEN_EXPIRY_REMEMBER = 30 * 24 * 3600  # 30 days


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength. Returns (ok, error_message)."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must include at least one digit"
    return True, ""


def create_token(user_id: int, name: str) -> str:
    payload = {
        "sub": user_id,
        "name": name,
        "exp": int(time.time()) + TOKEN_EXPIRY,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing auth token")
    token = auth[7:]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": payload["sub"], "name": payload["name"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Refresh tokens ──────────────────────────────────────────

def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_refresh_token(
    user_id: int, name: str, device_info: str = "", ip: str = "", remember_me: bool = False
) -> str:
    """Create a refresh token, store its hash in DB, return the raw token."""
    raw = secrets.token_urlsafe(48)
    token_hash = _hash_refresh_token(raw)
    expiry = REFRESH_TOKEN_EXPIRY_REMEMBER if remember_me else REFRESH_TOKEN_EXPIRY
    expires_at_sql = f"datetime('now', '+{expiry} seconds')"
    conn = get_db()
    try:
        conn.execute(
            f"INSERT INTO refresh_tokens (user_id, token_hash, device_info, ip_address, expires_at) "
            f"VALUES (?, ?, ?, ?, {expires_at_sql})",
            (user_id, token_hash, device_info, ip),
        )
        conn.commit()
    finally:
        conn.close()
    return raw


def verify_refresh_token(token: str) -> dict | None:
    """Verify a refresh token. Returns {id, name, token_hash} or None."""
    token_hash = _hash_refresh_token(token)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT rt.user_id, u.name, rt.token_hash FROM refresh_tokens rt "
            "JOIN users u ON u.id = rt.user_id "
            "WHERE rt.token_hash = ? AND rt.revoked = 0 AND rt.expires_at > datetime('now')",
            (token_hash,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {"id": row["user_id"], "name": row["name"], "token_hash": row["token_hash"]}


def rotate_refresh_token(
    old_token: str, device_info: str = "", ip: str = "", remember_me: bool = False
) -> tuple[str, str] | None:
    """Rotate: revoke old refresh token, issue new access + refresh tokens.
    Returns (access_token, new_refresh_token) or None if old token is invalid.
    """
    user = verify_refresh_token(old_token)
    if not user:
        return None
    # Revoke old
    conn = get_db()
    try:
        conn.execute(
            "UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = ?",
            (user["token_hash"],),
        )
        conn.commit()
    finally:
        conn.close()
    # Issue new
    access = create_token(user["id"], user["name"])
    refresh = create_refresh_token(user["id"], user["name"], device_info, ip, remember_me)
    return access, refresh


def revoke_user_sessions(user_id: int, except_token_hash: str | None = None):
    """Revoke all refresh tokens for a user, optionally keeping one."""
    conn = get_db()
    try:
        if except_token_hash:
            conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ? AND token_hash != ?",
                (user_id, except_token_hash),
            )
        else:
            conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?",
                (user_id,),
            )
        conn.commit()
    finally:
        conn.close()
