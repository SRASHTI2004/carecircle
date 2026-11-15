"""Helpers shared by the API routers."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi import HTTPException, Request

from ..clock import to_local
from ..permissions import Session


def profile_row(conn: sqlite3.Connection, session: Session) -> sqlite3.Row:
    """The signed-in session's profile row (404 if it vanished)."""
    row: sqlite3.Row | None = conn.execute("SELECT * FROM profiles WHERE id = ?", (session.profile_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Profile not found.")
    return row


def local_now(conn: sqlite3.Connection, session: Session) -> datetime:
    """Current time as naive local wall-clock time in the elder's timezone."""
    return to_local(profile_row(conn, session)["timezone"])


def client_ip(request: Request) -> str:
    """Best-effort client address used as a rate-limit key."""
    return request.client.host if request.client else "unknown"
