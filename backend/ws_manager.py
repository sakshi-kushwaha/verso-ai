import asyncio
import json
import logging
from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket subscriptions for upload progress broadcasts."""

    def __init__(self):
        self._lock = asyncio.Lock()
        # upload_id -> set of connected WebSockets
        self._subs: dict[int, set[WebSocket]] = {}

    async def subscribe_upload(self, upload_id: int, ws: WebSocket):
        async with self._lock:
            self._subs.setdefault(upload_id, set()).add(ws)

    async def unsubscribe_upload(self, upload_id: int, ws: WebSocket):
        async with self._lock:
            if upload_id in self._subs:
                self._subs[upload_id].discard(ws)
                if not self._subs[upload_id]:
                    del self._subs[upload_id]

    async def broadcast_upload_progress(
        self,
        upload_id: int,
        progress: int,
        stage: str,
        status: str | None = None,
        error: str | None = None,
    ):
        async with self._lock:
            clients = list(self._subs.get(upload_id, []))

        msg = json.dumps({
            "type": "progress",
            "upload_id": upload_id,
            "progress": progress,
            "stage": stage,
            "status": status,
            "error": error,
        })

        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                log.debug("Failed to send WS message for upload %s", upload_id)

    async def broadcast_reel_ready(self, upload_id: int, reel: dict):
        """Push a reel_ready event so the frontend can display it immediately."""
        async with self._lock:
            clients = list(self._subs.get(upload_id, []))

        msg = json.dumps({
            "type": "reel_ready",
            "upload_id": upload_id,
            "reel": reel,
        })

        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                log.debug("Failed to send reel_ready for upload %s", upload_id)

    async def broadcast_video_ready(self, upload_id: int, reel_id: int, video_path: str):
        """Push a video_ready event so the frontend can switch from image card to video."""
        async with self._lock:
            clients = list(self._subs.get(upload_id, []))

        msg = json.dumps({
            "type": "video_ready",
            "upload_id": upload_id,
            "reel_id": reel_id,
            "video_path": video_path,
        })

        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                log.debug("Failed to send video_ready for upload %s reel %s", upload_id, reel_id)

    async def broadcast_flashcard_ready(self, upload_id: int, flashcard: dict):
        """Push a flashcard_ready event so the frontend can display it immediately."""
        async with self._lock:
            clients = list(self._subs.get(upload_id, []))

        msg = json.dumps({
            "type": "flashcard_ready",
            "upload_id": upload_id,
            "flashcard": flashcard,
        })

        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                log.debug("Failed to send flashcard_ready for upload %s", upload_id)


manager = ConnectionManager()
