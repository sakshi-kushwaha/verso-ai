import jwt
from fastapi import WebSocket, status
from auth import SECRET_KEY, ALGORITHM


async def ws_authenticate(ws: WebSocket) -> dict | None:
    """Authenticate a WebSocket connection via ?token= query param.

    Returns the user dict ``{"id": ..., "name": ...}`` on success,
    or closes the socket with 1008 and returns ``None``.
    """
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": payload["sub"], "name": payload["name"]}
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return None
