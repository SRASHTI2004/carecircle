"""Dose slots, per-dose status classification and adherence percentages (pure logic + queries)."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from ..clock import fmt_slot, parse_slot

GRACE = timedelta(minutes=30)

TAKEN_ON_TIME, TAKEN_LATE, SKIPPED, MISSED, DUE, UPCOMING = (
    "taken_on_time",
    "taken_late",
    "skipped",
    "missed",
    "due",
    "upcoming",
)
RESOLVED = {TAKEN_ON_TIME, TAKEN_LATE, SKIPPED, MISSED}


def classify(scheduled: datetime, log_status: str | None, logged_at: datetime | None, now: datetime) -> str:
    """Status of a single scheduled dose at time `now`."""
    if log_status == "taken" and logged_at is not None:
        return TAKEN_ON_TIME if logged_at - scheduled <= GRACE else TAKEN_LATE
    if log_status == "skipped":
        return SKIPPED
    if now < scheduled:
        return UPCOMING
    if now <= scheduled + GRACE:
        return DUE
    return MISSED


def adherence_percent(counts: dict[str, int]) -> int | None:
    """% of resolved doses that were taken (on time or late); None if nothing resolved yet."""
    resolved = sum(counts.get(s, 0) for s in RESOLVED)
    if resolved == 0:
        return None
    taken = counts.get(TAKEN_ON_TIME, 0) + counts.get(TAKEN_LATE, 0)
    return round(100 * taken / resolved)


def slots_for(med: sqlite3.Row | dict[str, Any], first: date, last: date) -> list[datetime]:
    """All scheduled dose datetimes of a medication between two dates (inclusive)."""
    times: list[str] = json.loads(med["times"])
    start = date.fromisoformat(med["start_date"])
    end = date.fromisoformat(med["end_date"]) if med["end_date"] else None
    day = max(first, start)
    stop = min(last, end) if end else last
    slots: list[datetime] = []
    while day <= stop:
        for t in times:
            hour, minute = t.split(":")
            slots.append(datetime(day.year, day.month, day.day, int(hour), int(minute)))
        day += timedelta(days=1)
    return slots


def doses_between(
    conn: sqlite3.Connection, profile_id: int, first: date, last: date, now: datetime
) -> list[dict[str, Any]]:
    """Every scheduled dose in the date range with its current status, oldest first."""
    meds = conn.execute("SELECT * FROM medications WHERE profile_id = ?", (profile_id,)).fetchall()
    logs: dict[tuple[int, str], sqlite3.Row] = {}
    if meds:
        ids = [m["id"] for m in meds]
        marks = ",".join("?" * len(ids))
        for row in conn.execute(f"SELECT * FROM dose_logs WHERE medication_id IN ({marks})", ids):  # noqa: S608 - placeholders only
            logs[(row["medication_id"], row["scheduled_at"])] = row
    doses: list[dict[str, Any]] = []
    for med in meds:
        if med["archived"] and not _has_history(med, logs):
            continue
        for slot in slots_for(med, first, last):
            key = fmt_slot(slot)
            log = logs.get((med["id"], key))
            if med["archived"] and log is None:
                continue
            status = classify(slot, log["status"] if log else None, parse_slot(log["logged_at"]) if log else None, now)
            doses.append(
                {
                    "medication_id": med["id"],
                    "name": med["name"],
                    "dose": med["dose"],
                    "instructions": med["instructions"],
                    "kind": med["kind"],
                    "scheduled_at": key,
                    "status": status,
                    "logged_by": log["logged_by"] if log else None,
                    "logged_at": log["logged_at"] if log else None,
                }
            )
    doses.sort(key=lambda d: (d["scheduled_at"], d["name"]))
    return doses


def _has_history(med: sqlite3.Row, logs: dict[tuple[int, str], sqlite3.Row]) -> bool:
    return any(k[0] == med["id"] for k in logs)


def weekly_stats(conn: sqlite3.Connection, profile_id: int, now: datetime, days: int = 7) -> dict[str, Any]:
    """Adherence over the last `days` days (including today up to now): overall, per day and per item."""
    first = (now - timedelta(days=days - 1)).date()
    doses = [d for d in doses_between(conn, profile_id, first, now.date(), now) if d["status"] in RESOLVED]
    counts: dict[str, int] = defaultdict(int)
    per_day: dict[str, dict[str, int]] = {}
    per_med: dict[str, dict[str, int]] = {}
    for d in doses:
        counts[d["status"]] += 1
        per_day.setdefault(d["scheduled_at"][:10], defaultdict(int))[d["status"]] += 1
        per_med.setdefault(d["name"], defaultdict(int))[d["status"]] += 1
    daily = []
    for offset in range(days):
        day = (first + timedelta(days=offset)).isoformat()
        c = per_day.get(day, {})
        daily.append({"date": day, "percent": adherence_percent(c), "total": sum(c.values())})
    by_medicine = [
        {"name": name, "percent": adherence_percent(c), "total": sum(c.values()), "missed": c.get(MISSED, 0)}
        for name, c in sorted(per_med.items())
    ]
    return {
        "days": days,
        "percent": adherence_percent(counts),
        "counts": {s: counts.get(s, 0) for s in (TAKEN_ON_TIME, TAKEN_LATE, SKIPPED, MISSED)},
        "total": len(doses),
        "missed_by_medicine": {m["name"]: m["missed"] for m in by_medicine if m["missed"]},
        "daily": daily,
        "by_medicine": by_medicine,
    }
