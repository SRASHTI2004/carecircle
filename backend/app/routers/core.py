"""Auth, profile, medications, doses, appointments, comments, activity, contacts, settings, outbox."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from ..clock import fmt_slot, parse_slot, to_local, utcnow
from ..config import get_settings
from ..db import get_db
from ..permissions import Session, can, current_session, require
from ..schemas import (
    ALL_NOTIFY,
    AppointmentIn,
    CommentIn,
    ContactIn,
    ContactNotify,
    DoseAction,
    LoginIn,
    MedicationIn,
    ProfileCreate,
    SettingsIn,
)
from ..security import create_limiter, hash_token
from ..services import adherence, changes, profiles

router = APIRouter(prefix="/api")


def _profile(conn: sqlite3.Connection, session: Session) -> sqlite3.Row:
    row: sqlite3.Row | None = conn.execute("SELECT * FROM profiles WHERE id = ?", (session.profile_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Profile not found.")
    return row


def _now(conn: sqlite3.Connection, session: Session) -> datetime:
    return to_local(_profile(conn, session)["timezone"])


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------- auth & profile ----------


@router.post("/profiles", status_code=201)
def create_profile(body: ProfileCreate, request: Request, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    key = _client(request)
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
    token, profile_id, role = profiles.login(conn, body.passcode, _client(request))
    return {"token": token, "role": role, "profile_id": profile_id}


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request, conn: sqlite3.Connection = Depends(get_db), _: Session = Depends(current_session)
) -> Response:
    token = request.headers["authorization"][7:].strip()
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
    conn.commit()
    return Response(status_code=204)


@router.get("/me")
def me(conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(current_session)) -> dict[str, Any]:
    p = _profile(conn, session)
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


# ---------- medications ----------


def _med_out(row: sqlite3.Row) -> dict[str, Any]:
    import json

    return {
        "id": row["id"],
        "kind": row["kind"],
        "name": row["name"],
        "dose": row["dose"],
        "times": json.loads(row["times"]),
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "instructions": row["instructions"],
        "stock": row["stock"],
        "low_stock_threshold": row["low_stock_threshold"],
    }


@router.get("/medications")
def list_medications(
    conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("view"))
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM medications WHERE profile_id = ? AND archived = 0 ORDER BY name", (session.profile_id,)
    )
    return [_med_out(r) for r in rows]


def _check_duplicate(
    conn: sqlite3.Connection, profile_id: int, body: MedicationIn, allow: bool, exclude: int | None = None
) -> None:
    """Warn (409) when the same medicine/routine name already exists; the client may confirm and resend."""
    twin = changes.find_duplicate(conn, profile_id, body.name, exclude)
    if twin and not allow:
        raise HTTPException(
            409,
            f"'{twin}' is already on the list. Adding it twice can mean a double dose, so please check with a doctor "
            "or pharmacist. If you are sure, confirm to add it anyway.",
        )


@router.post("/medications", status_code=201)
def add_medication(
    body: MedicationIn,
    response: Response,
    allow_duplicate: bool = False,
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("edit_care")),
) -> dict[str, Any]:
    _check_duplicate(conn, session.profile_id, body, allow_duplicate)
    result = changes.submit_change(conn, session, "medication", "create", body.model_dump(mode="json"))
    response.status_code = 201 if result["status"] == "applied" else 202
    return result


@router.put("/medications/{med_id}")
def edit_medication(
    med_id: int,
    body: MedicationIn,
    response: Response,
    allow_duplicate: bool = False,
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("edit_care")),
) -> dict[str, Any]:
    _check_duplicate(conn, session.profile_id, body, allow_duplicate, med_id)
    result = changes.submit_change(
        conn, session, "medication", "update", {**body.model_dump(mode="json"), "id": med_id}
    )
    response.status_code = 200 if result["status"] == "applied" else 202
    return result


@router.delete("/medications/{med_id}")
def delete_medication(
    med_id: int,
    response: Response,
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("edit_care")),
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT name FROM medications WHERE id = ? AND profile_id = ? AND archived = 0", (med_id, session.profile_id)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "That medication was not found.")
    result = changes.submit_change(conn, session, "medication", "delete", {"id": med_id, "name": row["name"]})
    response.status_code = 200 if result["status"] == "applied" else 202
    return result


# ---------- doses & adherence ----------


@router.get("/doses/today")
def doses_today(
    conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("view"))
) -> dict[str, Any]:
    now = _now(conn, session)
    doses = adherence.doses_between(conn, session.profile_id, now.date(), now.date(), now)
    return {"now": fmt_slot(now), "doses": doses}


@router.post("/doses")
def log_dose(
    body: DoseAction, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("log_dose"))
) -> dict[str, Any]:
    now = _now(conn, session)
    med = conn.execute(
        "SELECT * FROM medications WHERE id = ? AND profile_id = ? AND archived = 0",
        (body.medication_id, session.profile_id),
    ).fetchone()
    if med is None:
        raise HTTPException(404, "That medication was not found.")
    try:
        slot = parse_slot(body.scheduled_at)
    except ValueError:
        raise HTTPException(422, "scheduled_at must look like 2025-01-31T08:00") from None
    valid = {fmt_slot(s) for s in adherence.slots_for(med, slot.date(), slot.date())}
    if fmt_slot(slot) not in valid:
        raise HTTPException(422, "That is not a scheduled dose for this medicine.")
    if slot.date() < now.date() - timedelta(days=1) or slot.date() > now.date():
        raise HTTPException(422, "Only today's and yesterday's doses can be marked.")
    existing = conn.execute(
        "SELECT status FROM dose_logs WHERE medication_id = ? AND scheduled_at = ?", (med["id"], fmt_slot(slot))
    ).fetchone()
    if body.action == "undo":
        if existing is None:
            raise HTTPException(409, "That dose has not been marked yet.")
        conn.execute("DELETE FROM dose_logs WHERE medication_id = ? AND scheduled_at = ?", (med["id"], fmt_slot(slot)))
    else:
        conn.execute(
            "INSERT INTO dose_logs (medication_id, scheduled_at, status, logged_at, logged_by) VALUES (?,?,?,?,?)"
            " ON CONFLICT(medication_id, scheduled_at) DO UPDATE SET status=excluded.status,"
            " logged_at=excluded.logged_at, logged_by=excluded.logged_by",
            (med["id"], fmt_slot(slot), body.action, fmt_slot(now), session.role),
        )
    # Keep the pill count honest when a dose flips between taken and not taken.
    was_taken = bool(existing and existing["status"] == "taken")
    if med["kind"] != "medicine":
        pass  # routines have no stock
    elif body.action == "taken" and not was_taken:
        conn.execute("UPDATE medications SET stock = MAX(stock - 1, 0) WHERE id = ?", (med["id"],))
    elif body.action != "taken" and was_taken:
        conn.execute("UPDATE medications SET stock = stock + 1 WHERE id = ?", (med["id"],))
    changes.log_activity(conn, session.profile_id, session.role, body.action, f"{med['name']} at {slot:%H:%M}")
    conn.commit()
    return {"status": body.action}


@router.get("/adherence/weekly")
def weekly(conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("view"))) -> dict[str, Any]:
    return adherence.weekly_stats(conn, session.profile_id, _now(conn, session))


# ---------- appointments ----------


def _appt_out(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in ("id", "doctor", "place", "starts_at", "notes")}


@router.get("/appointments")
def list_appointments(
    upcoming: bool = True, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("view"))
) -> list[dict[str, Any]]:
    now = fmt_slot(_now(conn, session))
    sql = "SELECT * FROM appointments WHERE profile_id = ? AND starts_at >= ? ORDER BY starts_at"
    if not upcoming:
        sql = "SELECT * FROM appointments WHERE profile_id = ? AND starts_at < ? ORDER BY starts_at DESC LIMIT 20"
    return [_appt_out(r) for r in conn.execute(sql, (session.profile_id, now))]


@router.post("/appointments", status_code=201)
def add_appointment(
    body: AppointmentIn,
    response: Response,
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("edit_care")),
) -> dict[str, Any]:
    payload = {**body.model_dump(mode="json"), "starts_at": fmt_slot(body.starts_at)}
    result = changes.submit_change(conn, session, "appointment", "create", payload)
    response.status_code = 201 if result["status"] == "applied" else 202
    return result


@router.put("/appointments/{appt_id}")
def edit_appointment(
    appt_id: int,
    body: AppointmentIn,
    response: Response,
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("edit_care")),
) -> dict[str, Any]:
    payload = {**body.model_dump(mode="json"), "starts_at": fmt_slot(body.starts_at), "id": appt_id}
    result = changes.submit_change(conn, session, "appointment", "update", payload)
    response.status_code = 200 if result["status"] == "applied" else 202
    return result


@router.delete("/appointments/{appt_id}")
def delete_appointment(
    appt_id: int,
    response: Response,
    conn: sqlite3.Connection = Depends(get_db),
    session: Session = Depends(require("edit_care")),
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT doctor FROM appointments WHERE id = ? AND profile_id = ?", (appt_id, session.profile_id)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "That appointment was not found.")
    result = changes.submit_change(conn, session, "appointment", "delete", {"id": appt_id, "doctor": row["doctor"]})
    response.status_code = 200 if result["status"] == "applied" else 202
    return result


# ---------- pending approval, activity, comments, contacts, outbox ----------


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
