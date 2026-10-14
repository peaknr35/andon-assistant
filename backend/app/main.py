"""FastAPI application entrypoint. Hosts the assistant (chat) + the Deep Research
Studio endpoints (now the deep_research tool's home)."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .logging_config import configure_logging
from .routes import chat, handoff, health, research

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


async def _calendar_sync_loop(minutes: int) -> None:
    """Periodically pull cloud calendar events into the local store (only when enabled)."""
    from .services.calendar_sync import any_enabled, sync_once
    interval = max(60, minutes * 60)
    while True:
        try:
            if any_enabled():
                counts = await asyncio.to_thread(sync_once)
                if counts:
                    logger.info("calendar sync: %s", counts)
        except Exception:  # pragma: no cover - defensive, never kill the loop
            logger.exception("calendar sync loop error")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .services.calendar_sync import any_enabled
    task = None
    if any_enabled():
        logger.info("calendar sync enabled; starting background refresh")
        task = asyncio.create_task(_calendar_sync_loop(settings.calendar_sync_minutes))
    try:
        yield
    finally:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Local-first personal agent + streaming deep research. Bring your own key.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(health.router)
app.include_router(research.router)
app.include_router(chat.router)
app.include_router(handoff.router)


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "health": "/health",
        "providers": "/providers",
        "assistant": "POST /chat/stream",
        "memory": "/memory",
        "research": "POST /research/stream",
    }
