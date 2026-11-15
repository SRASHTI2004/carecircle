"""Reminder rules: upcoming/missed dose, routines, appointments (1 day / 2 hours), low stock.

`run_reminders` is idempotent: each reminder has a unique key in `reminders_sent`, so running it
every minute (or from an external cron) never sends the same email twice. Recipients are chosen
by role and by each member's notification preferences.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta

from ..clock import fmt_slot, parse_slot, to_local, utcnow
from ..permissions import CARETAKER, ELDER, FAMILY
from .adherence import DUE, GRACE, MISSED, UPCOMING, doses_between
from .mailer import render_email, retry_failed, send_email

log = logging.getLogger("carecircle.reminders")

UPCOMING_WINDOW = timedelta(minutes=15)
MISSED_MAX_AGE = timedelta(hours=6)  # don't send stale "missed" emails after long downtime


def recipients(conn: sqlite3.Connection, profile_id: int, roles: tuple[str, ...], ntype: str) -> list[str]:
    """Unique emails of contacts with one of `roles` who opted in to `ntype`."""
    marks = ",".join("?" * len(roles))
    rows = conn.execute(
        f"SELECT email, notify FROM contacts WHERE profile_id = ? AND role IN ({marks})",  # noqa: S608 - placeholders only
        (profile_id, *roles),
    )
    seen: dict[str, None] = {}
    for r in rows:
        if ntype in json.loads(r["notify"] or "[]"):
            seen[r["email"]] = None
    return list(seen)


def notify(
    conn: sqlite3.Connection,
    profile: sqlite3.Row,
    key: str,
    roles: tuple[str, ...],
    ntype: str,
    subject: str,
    heading: str,
    message: str,
) -> int:
    """Send once per key to opted-in recipients. Returns the number of emails produced."""
    to = recipients(conn, profile["id"], roles, ntype)
    if not to:
        return 0
    if (
        conn.execute(
            "INSERT OR IGNORE INTO reminders_sent (key, sent_at) VALUES (?, ?)", (key, utcnow().isoformat())
        ).rowcount
        == 0
    ):
        return 0
    text, page = render_email(profile["name"], heading, message)
    for address in to:
        send_email(conn, profile["id"], address, subject, text, page)
    return len(to)


def _dose_reminders(conn: sqlite3.Connection, profile: sqlite3.Row, now: datetime) -> int:
    sent = 0
    kinds = {
        r["id"]: r["kind"]
        for r in conn.execute("SELECT id, kind FROM medications WHERE profile_id = ?", (profile["id"],))
    }
    name = profile["name"]
    window_start = (now - MISSED_MAX_AGE - GRACE).date()
    for d in doses_between(conn, profile["id"], window_start, now.date(), now):
        slot = parse_slot(d["scheduled_at"])
        when = slot.strftime("%H:%M")
        routine = kinds.get(d["medication_id"]) == "routine"
        what = f"{d['name']} ({d['dose']})" if d["dose"] else d["name"]
        extra = f" {d['instructions']}" if d["instructions"] else ""
        if d["status"] in (UPCOMING, DUE) and slot - UPCOMING_WINDOW <= now <= slot + timedelta(minutes=1):
            sent += notify(
                conn,
                profile,
                f"dose-up:{d['medication_id']}:{d['scheduled_at']}",
                (ELDER, CARETAKER),
                "routine" if routine else "dose_upcoming",
                f"{'Routine' if routine else 'Dose'} reminder: {d['name']} at {when}",
                f"{'Time for' if routine else 'Time to take'} {d['name']} at {when}",
                (f"{name} has {what} planned at {when}." if routine else f"{name} should take {what} at {when}.")
                + extra,
            )
        elif d["status"] == MISSED and now - slot <= MISSED_MAX_AGE:
            sent += notify(
                conn,
                profile,
                f"dose-miss:{d['medication_id']}:{d['scheduled_at']}",
                (CARETAKER, FAMILY),
                "routine" if routine else "dose_missed",
                f"Missed {'routine' if routine else 'dose'}: {name} - {d['name']} at {when}",
                f"{d['name']} was not marked done",
                f"{what} planned for {when} was not marked within 30 minutes. Please check in with {name}.",
            )
    return sent


def _appointment_reminders(conn: sqlite3.Connection, profile: sqlite3.Row, now: datetime) -> int:
    sent = 0
    rows = conn.execute(
        "SELECT * FROM appointments WHERE profile_id = ? AND starts_at > ? AND starts_at <= ?",
        (profile["id"], fmt_slot(now), fmt_slot(now + timedelta(days=1))),
    ).fetchall()
    everyone = (ELDER, CARETAKER, FAMILY)
    for a in rows:
        start = parse_slot(a["starts_at"])
        label = f"{profile['name']} sees {a['doctor']} at {a['place']} on {start:%A %d %b} at {start:%H:%M}."
        if a["notes"]:
            label += f"\nNotes: {a['notes']}"
        if now >= start - timedelta(hours=2):
            sent += notify(
                conn,
                profile,
                f"appt-2h:{a['id']}",
                everyone,
                "appointment",
                f"Appointment in 2 hours: {a['doctor']}",
                "Doctor visit in 2 hours",
                label,
            )
        else:
            sent += notify(
                conn,
                profile,
                f"appt-1d:{a['id']}",
                everyone,
                "appointment",
                f"Appointment tomorrow: {a['doctor']}",
                "Doctor visit tomorrow",
                label,
            )
    return sent


def _low_stock(conn: sqlite3.Connection, profile: sqlite3.Row, now: datetime) -> int:
    sent = 0
    today = now.date().isoformat()
    for m in conn.execute(
        "SELECT * FROM medications WHERE profile_id = ? AND archived = 0 AND kind = 'medicine' AND stock <= low_stock_threshold"
        " AND start_date <= ? AND (end_date IS NULL OR end_date >= ?)",
        (profile["id"], today, today),
    ):
        sent += notify(
            conn,
            profile,
            f"stock:{m['id']}:{today}",
            (ELDER, CARETAKER),
            "low_stock",
            f"Low stock: {m['name']}",
            f"Only {m['stock']} left of {m['name']}",
            f"Only {m['stock']} left of {m['name']} ({m['dose']}) for {profile['name']}. Time to refill.",
        )
    return sent


def run_reminders(conn: sqlite3.Connection, now_utc: datetime | None = None) -> dict[str, int]:
    """Evaluate all reminder rules for all profiles and retry failed deliveries."""
    totals = {"doses": 0, "appointments": 0, "low_stock": 0, "retried": 0}
    for profile in conn.execute("SELECT * FROM profiles").fetchall():
        now = to_local(profile["timezone"], now_utc)
        totals["doses"] += _dose_reminders(conn, profile, now)
        totals["appointments"] += _appointment_reminders(conn, profile, now)
        totals["low_stock"] += _low_stock(conn, profile, now)
    totals["retried"] = retry_failed(conn, now_utc)
    conn.commit()
    return totals
