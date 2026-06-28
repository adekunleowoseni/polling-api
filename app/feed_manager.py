from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


@dataclass
class FrameStore:
    jpeg: bytes | None = None
    people_count: int = 0
    updated_at: datetime | None = None


class FeedManager:
    def __init__(self) -> None:
        self._frames: dict[str, FrameStore] = {}
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    def get_frame(self, code: str) -> FrameStore:
        return self._frames.get(code, FrameStore())

    async def store_frame(self, code: str, jpeg: bytes, people_count: int) -> None:
        now = datetime.now(timezone.utc)
        async with self._lock:
            self._frames[code] = FrameStore(jpeg=jpeg, people_count=people_count, updated_at=now)
        await self.broadcast(
            {
                "type": "feed_update",
                "code": code,
                "people_count": people_count,
                "stream_status": "live",
                "last_frame_at": now.isoformat(),
            }
        )

    async def update_people_count(
        self, code: str, people_count: int, stream_status: str = "live"
    ) -> None:
        now = datetime.now(timezone.utc)
        async with self._lock:
            store = self._frames.get(code, FrameStore())
            store.people_count = people_count
            store.updated_at = now
            self._frames[code] = store
        last_frame_at = store.updated_at.isoformat() if store.updated_at else None
        await self.broadcast(
            {
                "type": "feed_update",
                "code": code,
                "people_count": people_count,
                "stream_status": stream_status,
                "last_frame_at": last_frame_at,
                "manual_correction": True,
            }
        )

    async def clear_frame(self, code: str) -> None:
        async with self._lock:
            self._frames.pop(code, None)
        await self.broadcast(
            {
                "type": "feed_update",
                "code": code,
                "people_count": 0,
                "stream_status": "offline",
                "last_frame_at": None,
                "forced_offline": True,
            }
        )

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


feed_manager = FeedManager()
