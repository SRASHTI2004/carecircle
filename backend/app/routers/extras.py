"""Passcode management, emergency info card, wellbeing check-ins and the test-email button."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..clock import utcnow
from ..config import get_settings
from ..db import get_db
from ..permissions import CARETAKER, ELDER, FAMILY, Session, require
from ..schemas import CheckinIn, EmergencyIn, TestEmailIn
from ..security import email_limiter
from ..services import changes, profiles
from ..services.mailer import render_email, send_email
from ..services.reminders import notify
from .common import profile_row

router = APIRouter(prefix="/api")
ROLES = (ELDER, CARETAKER, FAMILY)


# ---------- passcode management ----------


def _managed_roles(actor: str) -> tuple[str, ...]:
    """Elder manages every role; a caretaker manages the family passcode only."""
    return ROLES if actor == ELDER else (FAMILY,)


def _check_role(role: str, session: Session) -> None:
    if role not in ROLES:
        raise HTTPException(404, "Unknown role.")
    if role not in _managed_roles(session.role):
        raise HTTPException(403, "You can only manage the family passcode. Ask the elder for other roles.")


@router.get("/passcodes")
def list_passcodes(
    conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("manage_passcodes"))
) -> list[dict[str, Any]]:
    active = {r["role"] for r in conn.execute("SELECT role FROM passcodes WHERE profile_id = ?", (session.profile_id,))}
    return [{"role": r, "active": r in active, "can_manage": r in _managed_roles(session.role)} for r in ROLES]


@router.post("/passcodes/{role}/rotate")
def rotate(
    role: str, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("manage_passcodes"))
) -> dict[str, str]:
    _check_role(role, session)
    passcode = profiles.rotate_passcode(conn, session.profile_id, role, session.role)
    return {"role": role, "passcode": passcode, "note": "Share this now; it is shown only once."}


@router.delete("/passcodes/{role}")
def revoke(
    role: str, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("manage_passcodes"))
) -> dict[str, str]:
    _check_role(role, session)
    if role == session.role:
        raise HTTPException(409, "You cannot revoke your own passcode. Rotate it instead.")
    profiles.revoke_passcode(conn, session.profile_id, role, session.role)
    return {"status": "revoked"}


# ---------- test email ----------


@router.post("/settings/test-email")
def test_email(
    body: TestEmailIn,
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("manage_contacts")),
) -> dict[str, Any]:
    key = str(session.profile_id)
    wait = email_limiter.retry_after(key)
    if wait:
        raise HTTPException(
            429, f"Too many test emails. Try again in {wait} seconds.", headers={"Retry-After": str(wait)}
        )
    email_limiter.record_failure(key)
    profile = profile_row(conn, session)
    text, page = render_email(
        profile["name"],
        "Test email from CareCircle",
        "If you can read this, email reminders for missed doses, upcoming doses and appointments will reach you.",
    )
    delivered = send_email(conn, session.profile_id, body.email, "CareCircle test email", text, page)
    conn.commit()
    smtp = get_settings().smtp_configured
    if delivered:
        message = f"Test email sent to {body.email}."
    elif smtp:
        message = "Email could not be delivered right now; it will be retried. Check the Email reminders page."
    else:
        message = "Email (SMTP) is not configured on this server, so the message was added to the demo outbox instead."
    return {"delivered": delivered, "smtp_configured": smtp, "message": message}


# ---------- emergency card (the elder controls it) ----------


@router.get("/emergency")
def get_emergency(
    conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("view"))
) -> dict[str, Any]:
    profile = profile_row(conn, session)
    card = conn.execute("SELECT * FROM emergency_cards WHERE profile_id = ?", (session.profile_id,)).fetchone()
    fields = EmergencyIn().model_dump()
    data = {k: card[k] for k in fields} if card else fields
    meds = conn.execute(
        "SELECT name, dose, times, instructions FROM medications WHERE profile_id = ? AND archived = 0 AND kind = 'medicine'"
        " AND (end_date IS NULL OR end_date >= ?) ORDER BY name",
        (session.profile_id, utcnow().date().isoformat()),
    )
    contacts = conn.execute(
        "SELECT name, email, role FROM contacts WHERE profile_id = ? AND role IN ('caretaker','family') ORDER BY role, name",
        (session.profile_id,),
    )
    return {
        "name": profile["name"],
        **data,
        "updated_at": card["updated_at"] if card else "",
        "medicines": [
            {**{k: m[k] for k in ("name", "dose", "instructions")}, "times": json.loads(m["times"])} for m in meds
        ],
        "contacts": [dict(c) for c in contacts],
        "can_edit": session.role == ELDER,
    }


@router.put("/emergency")
def put_emergency(
    body: EmergencyIn, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("edit_emergency"))
) -> dict[str, str]:
    d = body.model_dump()
    cols = ", ".join(d)
    marks = ", ".join("?" * len(d))
    updates = ", ".join(f"{k} = excluded.{k}" for k in d)
    conn.execute(
        f"INSERT INTO emergency_cards (profile_id, {cols}, updated_at) VALUES (?, {marks}, ?)"  # noqa: S608 - fixed column names
        f" ON CONFLICT(profile_id) DO UPDATE SET {updates}, updated_at = excluded.updated_at",
        (session.profile_id, *d.values(), utcnow().isoformat()),
    )
    changes.log_activity(conn, session.profile_id, session.role, "updated", "emergency information card")
    conn.commit()
    return {"status": "saved"}


# ---------- wellbeing check-ins ----------


@router.post("/checkins", status_code=201)
def add_checkin(
    body: CheckinIn, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("checkin"))
) -> dict[str, Any]:
    profile = profile_row(conn, session)
    previous = conn.execute(
        "SELECT mood FROM checkins WHERE profile_id = ? ORDER BY id DESC LIMIT 1", (session.profile_id,)
    ).fetchone()
    cur = conn.execute(
        "INSERT INTO checkins (profile_id, mood, note, logged_by, created_at) VALUES (?,?,?,?,?)",
        (session.profile_id, body.mood, body.note, session.role, utcnow().isoformat()),
    )
    changes.log_activity(conn, session.profile_id, session.role, "checked in", f"feeling {body.mood}")
    alerted = 0
    if body.mood == "unwell" and previous is not None and previous["mood"] == "unwell":
        # Two "not well" check-ins in a row: tell the caretakers.
        note = f' They wrote: "{body.note}"' if body.note else ""
        alerted = notify(
            conn,
            profile,
            f"unwell:{cur.lastrowid}",
            (CARETAKER,),
            "wellbeing",
            f"Please check in: {profile['name']} reported not feeling well again",
            f"{profile['name']} is not feeling well",
            f"{profile['name']} answered 'not well' on two check-ins in a row.{note} Please call or visit.",
        )
    conn.commit()
    return {"status": "saved", "alerted": alerted}


@router.get("/checkins")
def list_checkins(
    limit: int = Query(14, ge=1, le=60),
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("view")),
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT mood, note, logged_by, created_at FROM checkins WHERE profile_id = ? ORDER BY id DESC LIMIT ?",
        (session.profile_id, limit),
    )
    return [dict(r) for r in rows]
