"""SQLite access. All queries elsewhere use parameter binding (never string formatting)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    require_approval INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS passcodes (
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    hash TEXT NOT NULL,
    PRIMARY KEY (profile_id, role)
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL,
    notify TEXT NOT NULL DEFAULT '["dose_upcoming","dose_missed","routine","appointment","low_stock","wellbeing"]'
);
CREATE TABLE IF NOT EXISTS medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    dose TEXT NOT NULL,
    times TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT,
    instructions TEXT NOT NULL DEFAULT '',
    stock INTEGER NOT NULL DEFAULT 0,
    low_stock_threshold INTEGER NOT NULL DEFAULT 5,
    archived INTEGER NOT NULL DEFAULT 0,
    kind TEXT NOT NULL DEFAULT 'medicine'
);
CREATE TABLE IF NOT EXISTS dose_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medication_id INTEGER NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    scheduled_at TEXT NOT NULL,
    status TEXT NOT NULL,
    logged_at TEXT NOT NULL,
    logged_by TEXT NOT NULL,
    UNIQUE (medication_id, scheduled_at)
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    doctor TEXT NOT NULL,
    place TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    entity TEXT NOT NULL,
    op TEXT NOT NULL,
    payload TEXT NOT NULL,
    summary TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders_sent (
    key TEXT PRIMARY KEY,
    sent_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    to_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    delivered INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    html TEXT NOT NULL DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT
);
CREATE TABLE IF NOT EXISTS emergency_cards (
    profile_id INTEGER PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    blood_group TEXT NOT NULL DEFAULT '',
    allergies TEXT NOT NULL DEFAULT '',
    conditions TEXT NOT NULL DEFAULT '',
    doctor_name TEXT NOT NULL DEFAULT '',
    doctor_phone TEXT NOT NULL DEFAULT '',
    emergency_contacts TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    mood TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    logged_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meds_profile ON medications(profile_id);
CREATE INDEX IF NOT EXISTS idx_appts_profile ON appointments(profile_id, starts_at);
CREATE INDEX IF NOT EXISTS idx_activity_profile ON activity_log(profile_id, id);
CREATE INDEX IF NOT EXISTS idx_outbox_profile ON outbox(profile_id, id);
CREATE INDEX IF NOT EXISTS idx_outbox_retry ON outbox(delivered, attempts);
CREATE INDEX IF NOT EXISTS idx_pending_profile ON pending_changes(profile_id, status);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_checkins_profile ON checkins(profile_id, id);
CREATE INDEX IF NOT EXISTS idx_comments_profile ON comments(profile_id, id);
CREATE INDEX IF NOT EXISTS idx_contacts_profile ON contacts(profile_id, role);
"""

# Columns added after the first release; applied to databases created by older versions.
MIGRATIONS = [
    ("medications", "kind", "TEXT NOT NULL DEFAULT 'medicine'"),
    (
        "contacts",
        "notify",
        'TEXT NOT NULL DEFAULT \'["dose_upcoming","dose_missed","routine","appointment","low_stock","wellbeing"]\'',
    ),
    ("outbox", "html", "TEXT NOT NULL DEFAULT ''"),
    ("outbox", "attempts", "INTEGER NOT NULL DEFAULT 0"),
    ("outbox", "last_attempt_at", "TEXT"),
]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        for table, column, ddl in MIGRATIONS:
            cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        conn.commit()
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
