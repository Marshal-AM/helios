"""WebSocket connection manager."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, asyncio.Task | None] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = None

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            task = self._connections.pop(websocket, None)
            if task and not task.done():
                task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass

    async def broadcast(self, message: dict[str, Any]) -> None:
        text = json.dumps(message)
        async with self._lock:
            sockets = list(self._connections.keys())
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def start_heartbeat(self, websocket: WebSocket, interval: int = 30) -> None:
        try:
            while True:
                await asyncio.sleep(interval)
                await websocket.send_json({"type": "ping"})
        except asyncio.CancelledError:
            return
        except Exception:
            await self.disconnect(websocket)

    def register_heartbeat(self, websocket: WebSocket, task: asyncio.Task) -> None:
        self._connections[websocket] = task

    @property
    def count(self) -> int:
        return len(self._connections)


ws_manager = ConnectionManager()
