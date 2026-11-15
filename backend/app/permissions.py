"""Role -> permission matrix and the FastAPI dependencies that enforce it."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends, Header, HTTPException, status

from .clock import utcnow
from .db import get_db
from .security import hash_token

ELDER, CARETAKER, FAMILY = "elder", "caretaker", "family"

PERMISSIONS: dict[str, frozenset[str]] = {
    ELDER: frozenset(
        {
            "view",
            "edit_care",
            "log_dose",
            "comment",
            "manage_settings",
            "approve",
            "use_ai",
            "manage_contacts",
            "checkin",
            "manage_passcodes",
            "edit_emergency",
        }
    ),
    CARETAKER: frozenset(
        {"view", "edit_care", "log_dose", "comment", "use_ai", "manage_contacts", "checkin", "manage_passcodes"}
    ),
    FAMILY: frozenset({"view", "comment"}),
}


def can(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, frozenset())


@dataclass(frozen=True)
class Session:
    profile_id: int
    role: str


def current_session(
    authorization: str | None = Header(default=None),
    conn: sqlite3.Connection = Depends(get_db),
) -> Session:
    """Resolve the bearer token to a session; every protected endpoint depends on this."""
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in again.")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise unauthorized
    token = authorization[7:].strip()
    row = conn.execute(
        "SELECT profile_id, role, expires_at FROM sessions WHERE token_hash = ?", (hash_token(token),)
    ).fetchone()
    if row is None or datetime.fromisoformat(row["expires_at"]) < utcnow():
        raise unauthorized
    return Session(profile_id=row["profile_id"], role=row["role"])


def require(permission: str) -> Callable[..., Session]:
    def dependency(session: Session = Depends(current_session)) -> Session:
        if not can(session.role, permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role is not allowed to do that.")
        return session

    return dependency
