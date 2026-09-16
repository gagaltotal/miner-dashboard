"""In-memory registry of live WebSocket connections, for broadcasting poll
updates and notifications to every open dashboard tab."""
from __future__ import annotations

import asyncio
import json
import logging

from starlette.websockets import WebSocket, WebSocketState

logger = logging.getLogger("miner_dashboard.ws")

# Hard cap on simultaneous WS connections: a home dashboard has a handful of
# tabs/devices open at once, so this is generous headroom while still
# bounding memory/fd usage if something tries to open many connections.
MAX_CONNECTIONS = 50


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> bool:
        async with self._lock:
            if len(self._connections) >= MAX_CONNECTIONS:
                return False
            self._connections.add(websocket)
        return True

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        payload = json.dumps(message)
        async with self._lock:
            targets = list(self._connections)
        for ws in targets:
            if ws.client_state != WebSocketState.CONNECTED:
                continue
            try:
                await ws.send_text(payload)
            except Exception:
                logger.debug("Dropping a WebSocket client that failed to receive a broadcast")
                await self.disconnect(ws)


manager = ConnectionManager()
