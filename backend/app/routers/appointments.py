"""Doctor appointments: upcoming list, add, edit and delete (with the elder-approval gate)."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from ..clock import fmt_slot
from ..db import get_db
from ..permissions import Session, require
from ..schemas import (
    AppointmentIn,
)
from ..services import changes
from .common import local_now

router = APIRouter(prefix="/api")


def _appt_out(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in ("id", "doctor", "place", "starts_at", "notes")}


@router.get("/appointments")
def list_appointments(
    upcoming: bool = True, conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("view"))
) -> list[dict[str, Any]]:
    now = fmt_slot(local_now(conn, session))
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
