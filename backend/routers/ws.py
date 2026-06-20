import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from deps import verify_ws_token
from ws.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = None):
    try:
        verify_ws_token(token)
    except ValueError:
        await websocket.close(code=4401)
        return

    await ws_manager.connect(websocket)
    heartbeat = asyncio.create_task(ws_manager.start_heartbeat(websocket, interval=30))
    ws_manager.register_heartbeat(websocket, heartbeat)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "pong":
                continue
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WebSocket closed: %s", exc)
    finally:
        heartbeat.cancel()
        await ws_manager.disconnect(websocket)
