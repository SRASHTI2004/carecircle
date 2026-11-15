"""Pending approvals, activity feed, family notes, reminder contacts and the email outbox."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ..clock import utcnow
from ..config import get_settings
from ..db import get_db
from ..permissions import Session, require
from ..schemas import (
    ALL_NOTIFY,
    CommentIn,
    ContactIn,
    ContactNotify,
)
from ..services import changes

router = APIRouter(prefix="/api")


@router.get("/pending")
def list_pending(
    conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("view"))
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, entity, op, summary, requested_by, created_at FROM pending_changes"
        " WHERE profile_id = ? AND status = 'pending' ORDER BY id DESC",
        (session.profile_id,),
    )
    return [dict(r) for r in rows]


@router.post("/pending/{change_id}/{decision}")
def decide_pending(
    change_id: int,
    decision: str,
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("approve")),
) -> dict[str, Any]:
    if decision not in ("approve", "reject"):
        raise HTTPException(404, "Unknown decision.")
    return changes.resolve_pending(conn, session.profile_id, change_id, decision == "approve")


@router.get("/activity")
def activity(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("view")),
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT actor_role, action, detail, created_at FROM activity_log WHERE profile_id = ?"
        " ORDER BY id DESC LIMIT ? OFFSET ?",
        (session.profile_id, limit, offset),
    )
    return [dict(r) for r in rows]


@router.get("/comments")
def list_comments(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("view")),
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT role, text, created_at FROM comments WHERE profile_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
        (session.profile_id, limit, offset),
    )
    return [dict(r) for r in rows]


@router.post("/comments", status_code=201)
def add_comment(
    body: CommentIn, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("comment"))
) -> dict[str, str]:
    conn.execute(
        "INSERT INTO comments (profile_id, role, text, created_at) VALUES (?,?,?,?)",
        (session.profile_id, session.role, body.text, utcnow().isoformat()),
    )
    changes.log_activity(conn, session.profile_id, session.role, "commented", body.text[:80])
    conn.commit()
    return {"status": "ok"}


@router.get("/contacts")
def list_contacts(
    conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("manage_contacts"))
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, name, email, role, notify FROM contacts WHERE profile_id = ? ORDER BY role, name",
        (session.profile_id,),
    )
    return [{**{k: r[k] for k in ("id", "name", "email", "role")}, "notify": json.loads(r["notify"])} for r in rows]


@router.post("/contacts", status_code=201)
def add_contact(
    body: ContactIn, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("manage_contacts"))
) -> dict[str, str]:
    conn.execute(
        "INSERT INTO contacts (profile_id, name, email, role, notify) VALUES (?,?,?,?,?)",
        (
            session.profile_id,
            body.name,
            body.email,
            body.role,
            json.dumps(body.notify if body.notify is not None else ALL_NOTIFY),
        ),
    )
    changes.log_activity(conn, session.profile_id, session.role, "added", f"reminder contact {body.name}")
    conn.commit()
    return {"status": "ok"}


@router.put("/contacts/{contact_id}/notify")
def set_contact_notify(
    contact_id: int,
    body: ContactNotify,
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("manage_contacts")),
) -> dict[str, list[str]]:
    chosen: list[str] = sorted(set(body.notify))
    cur = conn.execute(
        "UPDATE contacts SET notify = ? WHERE id = ? AND profile_id = ?",
        (json.dumps(chosen), contact_id, session.profile_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "That contact was not found.")
    changes.log_activity(conn, session.profile_id, session.role, "updated", "a member's email preferences")
    conn.commit()
    return {"notify": chosen}


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(
    contact_id: int, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("manage_contacts"))
) -> Response:
    conn.execute("DELETE FROM contacts WHERE id = ? AND profile_id = ?", (contact_id, session.profile_id))
    conn.commit()
    return Response(status_code=204)


@router.get("/outbox")
def outbox(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("view")),
) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT id, to_email, subject, body, delivered, error, created_at FROM outbox WHERE profile_id = ?"
        " ORDER BY id DESC LIMIT ? OFFSET ?",
        (session.profile_id, limit, offset),
    )
    return {"smtp_configured": get_settings().smtp_configured, "emails": [dict(r) for r in rows]}


__all__ = ["router"]
