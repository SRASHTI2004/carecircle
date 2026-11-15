"""Profile creation, passcode login/logout, the current profile and elder-only settings."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..db import get_db
from ..permissions import Session, can, current_session, require
from ..schemas import (
    LoginIn,
    ProfileCreate,
    SettingsIn,
)
from ..security import create_limiter, hash_token
from ..services import changes, profiles
from .common import client_ip, profile_row

router = APIRouter(prefix="/api")


@router.post("/profiles", status_code=201)
def create_profile(body: ProfileCreate, request: Request, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    """Create profile."""
    key = client_ip(request)
    wait = create_limiter.retry_after(key)
    if wait:
        raise HTTPException(
            429, "Too many profiles created from this device. Try later.", headers={"Retry-After": str(wait)}
        )
    create_limiter.record_failure(key)
    profile_id, passcodes = profiles.create_profile(conn, body.name, body.timezone, body.contacts)
    return {
        "profile_id": profile_id,
        "passcodes": passcodes,
        "note": "Save these passcodes now; they are shown only once.",
    }


@router.post("/auth/login")
def login(body: LoginIn, request: Request, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    """Login."""
    token, profile_id, role = profiles.login(conn, body.passcode, client_ip(request))
    return {"token": token, "role": role, "profile_id": profile_id}


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request, conn: sqlite3.Connection = Depends(get_db), _: Session = Depends(current_session)
) -> Response:
    """Logout."""
    token = request.headers["authorization"][7:].strip()
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
    conn.commit()
    return Response(status_code=204)


@router.get("/me")
def me(conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(current_session)) -> dict[str, Any]:
    """Me."""
    p = profile_row(conn, session)
    pending = conn.execute(
        "SELECT COUNT(*) FROM pending_changes WHERE profile_id = ? AND status = 'pending'", (p["id"],)
    ).fetchone()[0]
    return {
        "role": session.role,
        "profile": {
            "id": p["id"],
            "name": p["name"],
            "timezone": p["timezone"],
            "require_approval": bool(p["require_approval"]),
        },
        "pending_count": pending,
        "can_edit": can(session.role, "edit_care"),
    }


@router.put("/settings")
def update_settings(
    body: SettingsIn, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("manage_settings"))
) -> dict[str, bool]:
    """Update settings."""
    conn.execute(
        "UPDATE profiles SET require_approval = ? WHERE id = ?", (int(body.require_approval), session.profile_id)
    )
    changes.log_activity(
        conn,
        session.profile_id,
        session.role,
        "settings",
        "now requires elder approval for others' changes" if body.require_approval else "no longer requires approval",
    )
    conn.commit()
    return {"require_approval": body.require_approval}
