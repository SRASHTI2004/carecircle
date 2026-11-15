"""Create/update/delete of medications and appointments, with the elder-approval gate.

Every mutation goes through `submit_change`. If the elder has turned on "require my approval"
and a non-elder makes the change, it is queued as a pending change instead of being applied.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import HTTPException

from ..clock import utcnow
from ..permissions import ELDER, Session

ENTITIES = {"medication", "appointment"}


def log_activity(conn: sqlite3.Connection, profile_id: int, role: str, action: str, detail: str) -> None:
    conn.execute(
        "INSERT INTO activity_log (profile_id, actor_role, action, detail, created_at) VALUES (?,?,?,?,?)",
        (profile_id, role, action, detail, utcnow().isoformat()),
    )


def _describe(entity: str, op: str, payload: dict[str, Any]) -> str:
    label = payload.get("name") if entity == "medication" else payload.get("doctor")
    return f"{op} {entity}" + (f" '{label}'" if label else "")


def _exists(conn: sqlite3.Connection, profile_id: int, entity: str, item_id: int) -> sqlite3.Row:
    table = "medications" if entity == "medication" else "appointments"
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ? AND profile_id = ?", (item_id, profile_id)).fetchone()  # noqa: S608 - fixed table names
    if row is None:
        raise HTTPException(404, f"That {entity} was not found.")
    return row


def apply_change(conn: sqlite3.Connection, profile_id: int, entity: str, op: str, payload: dict[str, Any]) -> int:
    """Perform the change. Payload was already validated by the Pydantic request model."""
    if entity == "medication":
        if op == "create":
            cur = conn.execute(
                "INSERT INTO medications (profile_id, name, dose, times, start_date, end_date, instructions, stock, low_stock_threshold)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (profile_id, payload["name"], payload["dose"], json.dumps(payload["times"]), payload["start_date"],
                 payload.get("end_date"), payload.get("instructions", ""), payload.get("stock", 0),
                 payload.get("low_stock_threshold", 5)),
            )
            return int(cur.lastrowid or 0)
        item_id = int(payload["id"])
        _exists(conn, profile_id, entity, item_id)
        if op == "update":
            conn.execute(
                "UPDATE medications SET name=?, dose=?, times=?, start_date=?, end_date=?, instructions=?, stock=?,"
                " low_stock_threshold=? WHERE id=? AND profile_id=?",
                (payload["name"], payload["dose"], json.dumps(payload["times"]), payload["start_date"],
                 payload.get("end_date"), payload.get("instructions", ""), payload.get("stock", 0),
                 payload.get("low_stock_threshold", 5), item_id, profile_id),
            )
        else:  # delete = archive, so adherence history is kept
            conn.execute("UPDATE medications SET archived = 1 WHERE id=? AND profile_id=?", (item_id, profile_id))
        return item_id

    if op == "create":
        cur = conn.execute(
            "INSERT INTO appointments (profile_id, doctor, place, starts_at, notes) VALUES (?,?,?,?,?)",
            (profile_id, payload["doctor"], payload["place"], payload["starts_at"], payload.get("notes", "")),
        )
        return int(cur.lastrowid or 0)
    item_id = int(payload["id"])
    _exists(conn, profile_id, entity, item_id)
    if op == "update":
        conn.execute(
            "UPDATE appointments SET doctor=?, place=?, starts_at=?, notes=? WHERE id=? AND profile_id=?",
            (payload["doctor"], payload["place"], payload["starts_at"], payload.get("notes", ""), item_id, profile_id),
        )
    else:
        conn.execute("DELETE FROM appointments WHERE id=? AND profile_id=?", (item_id, profile_id))
    return item_id


def submit_change(
    conn: sqlite3.Connection, session: Session, entity: str, op: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Apply a change now, or queue it for the elder's approval. Returns {status, id}."""
    if entity not in ENTITIES or op not in {"create", "update", "delete"}:
        raise HTTPException(400, "Unsupported change.")
    if op != "create":
        _exists(conn, session.profile_id, entity, int(payload["id"]))
    profile = conn.execute("SELECT require_approval FROM profiles WHERE id = ?", (session.profile_id,)).fetchone()
    summary = _describe(entity, op, payload)
    if profile and profile["require_approval"] and session.role != ELDER:
        cur = conn.execute(
            "INSERT INTO pending_changes (profile_id, entity, op, payload, summary, requested_by, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (session.profile_id, entity, op, json.dumps(payload), summary, session.role, utcnow().isoformat()),
        )
        log_activity(conn, session.profile_id, session.role, "requested", f"{summary} (waiting for elder approval)")
        conn.commit()
        return {"status": "pending", "id": cur.lastrowid}
    item_id = apply_change(conn, session.profile_id, entity, op, payload)
    log_activity(conn, session.profile_id, session.role, op, summary)
    conn.commit()
    return {"status": "applied", "id": item_id}


def resolve_pending(conn: sqlite3.Connection, profile_id: int, change_id: int, approve: bool) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM pending_changes WHERE id = ? AND profile_id = ? AND status = 'pending'", (change_id, profile_id)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "That pending change was not found.")
    if approve:
        try:
            apply_change(conn, profile_id, row["entity"], row["op"], json.loads(row["payload"]))
        except HTTPException:
            conn.execute("UPDATE pending_changes SET status = 'rejected' WHERE id = ?", (change_id,))
            conn.commit()
            raise HTTPException(409, "The item changed or was removed, so this request could not be applied.") from None
    conn.execute("UPDATE pending_changes SET status = ? WHERE id = ?", ("approved" if approve else "rejected", change_id))
    log_activity(conn, profile_id, ELDER, "approved" if approve else "rejected", row["summary"])
    conn.commit()
    return {"status": "approved" if approve else "rejected"}
