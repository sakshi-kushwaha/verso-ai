import os
import time
import bcrypt
import jwt
from fastapi import Request, HTTPException

SECRET_KEY = os.getenv("JWT_SECRET", "verso-dev-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRY = 7 * 24 * 3600  # 7 days


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


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
