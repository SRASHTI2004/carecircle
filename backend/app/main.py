"""FastAPI application: JSON API under /api plus the built React app served as static files."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint

from .config import ROOT, get_settings
from .db import connect, init_db
from .routers import ai, appointments, auth, collaboration, doses, extras, medications, reminders
from .services.reminders import run_reminders
from .services.seed import seed_demo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("carecircle")
DIST = ROOT / "frontend" / "dist"

MAX_JSON_BODY_BYTES = 64 * 1024  # every JSON body in this API is tiny
MAX_UPLOAD_BODY_BYTES = 6 * 1024 * 1024  # prescription photos (5 MB) plus form overhead
UPLOAD_PATH = "/api/ai/prescription"

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
    """Create the schema, seed the demo profile and run the reminder scheduler."""
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
    """Create app."""
    app = FastAPI(title="CareCircle", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Reminder-Token"],
    )

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Reject oversized request bodies before they are read (413)."""
        limit = MAX_UPLOAD_BODY_BYTES if request.url.path == UPLOAD_PATH else MAX_JSON_BODY_BYTES
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > limit:
            return JSONResponse(status_code=413, content={"detail": "That request is too large."})
        return await call_next(request)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Log unexpected errors server-side only; the client never sees a stack trace or internals."""
        log.error("unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})

    @app.middleware("http")
    async def security_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Add security headers to every response."""
        response: Response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=()")
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if request.url.path.startswith("/api"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        """One readable message string, like every other error response ({"detail": "..."})."""
        parts = [f"{'.'.join(str(p) for p in e['loc'][1:]) or 'request'}: {e['msg']}" for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "; ".join(parts)})

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """Liveness probe used by Render."""
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(medications.router)
    app.include_router(doses.router)
    app.include_router(appointments.router)
    app.include_router(collaboration.router)
    app.include_router(reminders.router)
    app.include_router(extras.router)
    app.include_router(ai.router)

    if DIST.exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            """Serve a built frontend file, falling back to index.html for client-side routes."""
            if path.startswith("api/"):
                raise HTTPException(404)
            candidate = (DIST / path).resolve()
            if path and candidate.is_file() and DIST.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(DIST / "index.html")

    return app


app = create_app()
__all__ = ["app", "create_app"]
