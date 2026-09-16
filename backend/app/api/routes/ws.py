"""
WebSocket endpoint for live device updates and notifications.

The WS handshake is a normal HTTP request under the hood, so the browser
attaches the same-origin session cookie automatically — we validate it here
exactly like `require_session` does for REST routes, and close the socket
before accepting if it's missing/invalid. This means an unauthenticated
client cannot open a live feed of the dashboard's data by hitting the `/ws`
path directly.
"""
from __future__ import annotations

from fastapi import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.config import settings
from app.security.auth import verify_token
from app.services.connection_manager import manager

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    token = websocket.cookies.get(settings.COOKIE_NAME)
    if not token or verify_token(token) is None:
        await websocket.close(code=4401)
        return

    accepted = await manager.connect(websocket)
    if not accepted:
        await websocket.close(code=4429)  # too many connections
        return

    await websocket.accept()
    try:
        while True:
            # We don't expect inbound messages, but we must keep reading so
            # a client-initiated close is detected promptly instead of
            # leaking a half-open connection slot.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
