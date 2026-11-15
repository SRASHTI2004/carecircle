"""Demo profile with sample medicines, appointments and two weeks of adherence history."""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import timedelta

from ..clock import fmt_slot, to_local, utcnow
from ..config import get_settings
from ..schemas import ContactIn
from .adherence import slots_for
from .changes import log_activity
from .profiles import create_profile

DEMO_CODE = "DEMO"
DEMO_PASSCODES = {"elder": "DEMO-ELDER24", "caretaker": "DEMO-CARER24", "family": "DEMO-FAMILY24"}


def seed_demo(conn: sqlite3.Connection) -> bool:
    """Create the demo profile if it does not exist yet. Returns True if created."""
    if conn.execute("SELECT 1 FROM profiles WHERE code = ?", (DEMO_CODE,)).fetchone():
        return False
    tz = get_settings().default_timezone
    contacts = [
        ContactIn(name="Priya (caretaker)", email="caretaker@example.com", role="caretaker"),
        ContactIn(name="Arjun (son)", email="arjun@example.com", role="family"),
        ContactIn(name="Meera (daughter)", email="meera@example.com", role="family"),
        ContactIn(name="Margaret", email="margaret@example.com", role="elder"),
    ]
    pid, _ = create_profile(conn, "Margaret Sharma", tz, contacts, code=DEMO_CODE, passcodes=dict(DEMO_PASSCODES))
    now = to_local(tz)
    today = now.date()
    start = (today - timedelta(days=21)).isoformat()
    meds = [
        ("Metformin", "500 mg", ["08:00", "20:00"], "After food", 40, 8),
        ("Amlodipine", "5 mg", ["09:00"], "Morning, with water", 4, 5),  # low stock: shows the reminder
        ("Vitamin D3", "1000 IU", ["13:00"], "With lunch", 30, 5),
        ("Atorvastatin", "10 mg", ["21:30"], "Before bed", 25, 5),
        ("Blood pressure check", "", ["07:30"], "Sit quietly for 5 minutes first; note the reading", 0, 0),
        ("Evening walk", "", ["17:30"], "20 minutes, gentle pace", 0, 0),
        ("Drink a glass of water", "", ["11:00", "15:00"], "", 0, 0),
    ]
    rng = random.Random(7)  # noqa: S311 - deterministic demo data, not security
    for name, dose, times, instr, stock, threshold in meds:
        cur = conn.execute(
            "INSERT INTO medications (profile_id, name, dose, times, start_date, instructions, stock, low_stock_threshold, kind)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (pid, name, dose, json.dumps(times), start, instr, stock, threshold, "medicine" if dose else "routine"),
        )
        med_id = cur.lastrowid
        row = {"times": json.dumps(times), "start_date": start, "end_date": None}
        for slot in slots_for(row, today - timedelta(days=14), today):
            if slot >= now - timedelta(hours=1):
                continue  # leave today's remaining doses for the live demo
            roll = rng.random()
            if roll < 0.80:
                logged, status = slot + timedelta(minutes=rng.randint(0, 20)), "taken"
            elif roll < 0.90:
                logged, status = slot + timedelta(minutes=rng.randint(45, 150)), "taken"
            elif roll < 0.94:
                logged, status = slot + timedelta(minutes=5), "skipped"
            else:
                continue  # missed
            conn.execute(
                "INSERT INTO dose_logs (medication_id, scheduled_at, status, logged_at, logged_by) VALUES (?,?,?,?,?)",
                (med_id, fmt_slot(slot), status, fmt_slot(logged), "elder"),
            )
    appts = [
        (
            "Dr. Rao (Cardiologist)",
            "Apollo Clinic, Indiranagar",
            now + timedelta(days=1, hours=2),
            "Bring recent BP readings.",
        ),
        ("Dr. Mehta (GP)", "City Health Centre", now + timedelta(days=8), "Routine check-up and blood sugar test."),
        ("Dr. Iyer (Eye specialist)", "Vision Care", now - timedelta(days=12), "Annual eye test."),
    ]
    for doctor, place, when, notes in appts:
        conn.execute(
            "INSERT INTO appointments (profile_id, doctor, place, starts_at, notes) VALUES (?,?,?,?,?)",
            (pid, doctor, place, fmt_slot(when), notes),
        )
    for role, text in [
        ("family", "Mom, remember your walk after lunch today!"),
        ("caretaker", "BP was 128/82 this morning."),
    ]:
        conn.execute(
            "INSERT INTO comments (profile_id, role, text, created_at) VALUES (?,?,?,?)",
            (pid, role, text, utcnow().isoformat()),
        )
    conn.execute(
        "INSERT INTO emergency_cards (profile_id, blood_group, allergies, conditions, doctor_name, doctor_phone,"
        " emergency_contacts, notes, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            pid,
            "B+",
            "Penicillin",
            "Type 2 diabetes, high blood pressure",
            "Dr. Mehta (GP)",
            "+91 80 5550 0100",
            "Priya (caretaker) +91 98450 00001; Arjun (son) +91 98450 00002",
            "Wears reading glasses. Prefers Hindi or English.",
            utcnow().isoformat(),
        ),
    )
    for days_ago, mood, note in [(3, "good", ""), (2, "okay", "A bit tired"), (1, "good", "")]:
        conn.execute(
            "INSERT INTO checkins (profile_id, mood, note, logged_by, created_at) VALUES (?,?,?,?,?)",
            (pid, mood, note, "elder", (utcnow() - timedelta(days=days_ago)).isoformat()),
        )
    log_activity(conn, pid, "caretaker", "create", "medication 'Atorvastatin'")
    log_activity(conn, pid, "elder", "taken", "Metformin at 08:00")
    conn.commit()
    return True
