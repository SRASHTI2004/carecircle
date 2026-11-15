"""Reminder rules: upcoming dose, missed dose, appointment (1 day / 2 hours before), low stock.

`run_reminders` is idempotent: each reminder has a unique key in `reminders_sent`, so running
it every minute (or from an external cron) never sends the same email twice.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from ..clock import fmt_slot, parse_slot, to_local, utcnow
from ..permissions import CARETAKER, ELDER, FAMILY
from .adherence import DUE, GRACE, MISSED, UPCOMING, doses_between
from .mailer import send_email

UPCOMING_WINDOW = timedelta(minutes=15)
MISSED_MAX_AGE = timedelta(hours=6)  # don't send stale "missed" emails after long downtime


def _recipients(conn: sqlite3.Connection, profile_id: int, roles: tuple[str, ...]) -> list[str]:
    marks = ",".join("?" * len(roles))
    rows = conn.execute(f"SELECT DISTINCT email FROM contacts WHERE profile_id = ? AND role IN ({marks})", (profile_id, *roles))  # noqa: S608
    return [r["email"] for r in rows]


def _notify(conn: sqlite3.Connection, profile_id: int, key: str, roles: tuple[str, ...], subject: str, body: str) -> int:
    """Send once per key. Returns the number of emails produced."""
    to = _recipients(conn, profile_id, roles)
    if not to:
        return 0
    if conn.execute("INSERT OR IGNORE INTO reminders_sent (key, sent_at) VALUES (?, ?)", (key, utcnow().isoformat())).rowcount == 0:
        return 0
    footer = "\n\n-- CareCircle. This is a reminder, not medical advice; ask a doctor or pharmacist about any concern."
    for address in to:
        send_email(conn, profile_id, address, subject, body + footer)
    return len(to)


def _dose_reminders(conn: sqlite3.Connection, profile: sqlite3.Row, now: datetime) -> int:
    sent = 0
    name = profile["name"]
    window_start = (now - MISSED_MAX_AGE - GRACE).date()
    for d in doses_between(conn, profile["id"], window_start, now.date(), now):
        slot = parse_slot(d["scheduled_at"])
        when = slot.strftime("%H:%M")
        if d["status"] in (UPCOMING, DUE) and slot - UPCOMING_WINDOW <= now <= slot + timedelta(minutes=1):
            sent += _notify(
                conn, profile["id"], f"dose-up:{d['medication_id']}:{d['scheduled_at']}", (ELDER, CARETAKER),
                f"Dose reminder: {d['name']} at {when}",
                f"{name} should take {d['name']} ({d['dose']}) at {when}. {d['instructions']}".strip(),
            )
        elif d["status"] == MISSED and now - slot <= MISSED_MAX_AGE:
            sent += _notify(
                conn, profile["id"], f"dose-miss:{d['medication_id']}:{d['scheduled_at']}", (CARETAKER, FAMILY),
                f"Missed dose: {name} - {d['name']} at {when}",
                f"{d['name']} ({d['dose']}) scheduled for {when} was not marked as taken within 30 minutes. "
                f"Please check in with {name}.",
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
        if now >= start - timedelta(hours=2):
            sent += _notify(conn, profile["id"], f"appt-2h:{a['id']}", everyone, f"Appointment in 2 hours: {a['doctor']}", label)
        else:
            sent += _notify(conn, profile["id"], f"appt-1d:{a['id']}", everyone, f"Appointment tomorrow: {a['doctor']}", label)
    return sent


def _low_stock(conn: sqlite3.Connection, profile: sqlite3.Row, now: datetime) -> int:
    sent = 0
    today = now.date().isoformat()
    for m in conn.execute(
        "SELECT * FROM medications WHERE profile_id = ? AND archived = 0 AND stock <= low_stock_threshold"
        " AND start_date <= ? AND (end_date IS NULL OR end_date >= ?)",
        (profile["id"], today, today),
    ):
        sent += _notify(
            conn, profile["id"], f"stock:{m['id']}:{today}", (ELDER, CARETAKER),
            f"Low stock: {m['name']}",
            f"Only {m['stock']} left of {m['name']} ({m['dose']}) for {profile['name']}. Time to refill.",
        )
    return sent


def run_reminders(conn: sqlite3.Connection, now_utc: datetime | None = None) -> dict[str, int]:
    """Evaluate all reminder rules for all profiles. Returns counts of emails produced."""
    totals = {"doses": 0, "appointments": 0, "low_stock": 0}
    for profile in conn.execute("SELECT * FROM profiles").fetchall():
        now = to_local(profile["timezone"], now_utc)
        totals["doses"] += _dose_reminders(conn, profile, now)
        totals["appointments"] += _appointment_reminders(conn, profile, now)
        totals["low_stock"] += _low_stock(conn, profile, now)
    conn.commit()
    return totals
