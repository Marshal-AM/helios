import asyncio
import json
import logging
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from helios_common.db import async_engine  # noqa: E402
from helios_common.events import subscribe_events  # noqa: E402
from routers import aois, alerts, auth, changes, detections, export, scenes, ws  # noqa: E402
from ws.manager import ws_manager  # noqa: E402

logger = logging.getLogger(__name__)
_loop: asyncio.AbstractEventLoop | None = None


def _redis_listener() -> None:
    pubsub = subscribe_events()
    for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = json.loads(message["data"])
        except (json.JSONDecodeError, TypeError):
            continue
        if _loop and not _loop.is_closed():
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(data), _loop)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop
    _loop = asyncio.get_running_loop()
    thread = threading.Thread(target=_redis_listener, daemon=True)
    thread.start()
    logger.info("Redis event listener started")
    yield
    _loop = None


app = FastAPI(title="Helios API", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(aois.router)
app.include_router(detections.router)
app.include_router(changes.router)
app.include_router(alerts.router)
app.include_router(scenes.router)
app.include_router(export.router)
app.include_router(ws.router)


@app.get("/health")
async def health():
    db_status = "disconnected"
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as exc:
        return {"status": "degraded", "db": db_status, "error": str(exc), "phase": 5}

    return {"status": "ok", "db": db_status, "phase": 5, "ws_clients": ws_manager.count}


@app.get("/")
async def root():
    return {"service": "helios-api", "phase": 5}
