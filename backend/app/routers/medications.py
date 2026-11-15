"""Medicines and daily routines: list, add, edit and archive (with the elder-approval gate)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from ..db import get_db
from ..permissions import Session, require
from ..schemas import (
    MedicationIn,
)
from ..services import changes

router = APIRouter(prefix="/api")


def _med_out(row: sqlite3.Row) -> dict[str, Any]:
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
