"""Today's doses, marking doses taken/skipped/undone, and weekly adherence."""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..clock import fmt_slot, parse_slot
from ..db import get_db
from ..permissions import Session, require
from ..schemas import (
    DoseAction,
)
from ..services import adherence, changes
from .common import local_now

router = APIRouter(prefix="/api")

MARKABLE_DAYS_BACK = 1  # doses from today and yesterday can be marked


@router.get("/doses/today")
def doses_today(
    conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("view"))
) -> dict[str, Any]:
    now = local_now(conn, session)
    doses = adherence.doses_between(conn, session.profile_id, now.date(), now.date(), now)
    return {"now": fmt_slot(now), "doses": doses}


@router.post("/doses")
def log_dose(
    body: DoseAction, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("log_dose"))
) -> dict[str, Any]:
    now = local_now(conn, session)
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
    if slot.date() < now.date() - timedelta(days=MARKABLE_DAYS_BACK) or slot.date() > now.date():
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
    return adherence.weekly_stats(conn, session.profile_id, local_now(conn, session))
