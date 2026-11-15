"""FastAPI application: JSON API under /api plus the built React app served as static files."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import ROOT, get_settings
from .db import connect, init_db
from .routers import core, reminders
from .services.reminders import run_reminders
from .services.seed import seed_demo

log = logging.getLogger("carecircle")
DIST = ROOT / "frontend" / "dist"

CSP = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
)


def _reminder_tick() -> None:
    conn = connect()
    try:
        run_reminders(conn)
    except Exception:  # keep the scheduler alive; never log message content
        log.exception("reminder run failed")
    finally:
        conn.close()


async def _scheduler() -> None:
    while True:
        await asyncio.sleep(60)
        await asyncio.to_thread(_reminder_tick)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    conn = connect()
    try:
        seed_demo(conn)
    finally:
        conn.close()
    task = None if get_settings().disable_scheduler else asyncio.create_task(_scheduler())
    yield
    if task:
        task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="CareCircle", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Reminder-Token"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=()")
        if request.url.path.startswith("/api"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(core.router)
    app.include_router(reminders.router)
    try:
        from .routers import ai

        app.include_router(ai.router)
    except ImportError:  # AI router is optional
        pass

    if DIST.exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(404)
            candidate = (DIST / path).resolve()
            if path and candidate.is_file() and DIST.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(DIST / "index.html")

    return app


app = create_app()
__all__ = ["app", "create_app"]
