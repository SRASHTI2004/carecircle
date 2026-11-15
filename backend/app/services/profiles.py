"""Profile creation and passcode login."""
from __future__ import annotations

import sqlite3

from fastapi import HTTPException

from ..clock import utcnow, valid_timezone
from ..permissions import CARETAKER, ELDER, FAMILY
from ..security import (
    client_limiter,
    hash_passcode,
    new_passcode,
    new_token,
    profile_limiter,
    random_code,
    session_expiry,
    verify_passcode,
)
from ..schemas import ContactIn
from .changes import log_activity

ROLES = (ELDER, CARETAKER, FAMILY)


def create_profile(
    conn: sqlite3.Connection,
    name: str,
    timezone: str,
    contacts: list[ContactIn],
    code: str | None = None,
    passcodes: dict[str, str] | None = None,
) -> tuple[int, dict[str, str]]:
    """Create a profile and one passcode per role. Returns (id, plaintext passcodes) - shown once."""
    if not valid_timezone(timezone):
        raise HTTPException(422, "Unknown timezone.")
    code = code or random_code(4)
    while conn.execute("SELECT 1 FROM profiles WHERE code = ?", (code,)).fetchone():
        code = random_code(4)
    cur = conn.execute(
        "INSERT INTO profiles (code, name, timezone, created_at) VALUES (?,?,?,?)",
        (code, name, timezone, utcnow().isoformat()),
    )
    profile_id = int(cur.lastrowid or 0)
    plain = passcodes or {role: new_passcode(code) for role in ROLES}
    for role, passcode in plain.items():
        conn.execute(
            "INSERT INTO passcodes (profile_id, role, hash) VALUES (?,?,?)", (profile_id, role, hash_passcode(passcode))
        )
    for c in contacts:
        conn.execute(
            "INSERT INTO contacts (profile_id, name, email, role) VALUES (?,?,?,?)", (profile_id, c.name, c.email, c.role)
        )
    log_activity(conn, profile_id, ELDER, "created", f"care profile for {name}")
    conn.commit()
    return profile_id, plain


def login(conn: sqlite3.Connection, passcode: str, client: str) -> tuple[str, int, str]:
    """Check a passcode, enforce rate limits, issue a session token. Returns (token, profile_id, role)."""
    code = passcode.strip().upper().split("-", 1)[0]
    client_key, profile_key = f"{client}|{code}", code
    wait = max(client_limiter.retry_after(client_key), profile_limiter.retry_after(profile_key))
    if wait:
        raise HTTPException(429, f"Too many wrong passcodes. Try again in {wait} seconds.", headers={"Retry-After": str(wait)})

    profile = conn.execute("SELECT id FROM profiles WHERE code = ?", (code,)).fetchone()
    role: str | None = None
    if profile:
        for row in conn.execute("SELECT role, hash FROM passcodes WHERE profile_id = ?", (profile["id"],)):
            if verify_passcode(passcode.strip().upper(), row["hash"]):
                role = row["role"]
                break
    if profile is None or role is None:
        client_limiter.record_failure(client_key)
        profile_limiter.record_failure(profile_key)
        raise HTTPException(401, "That passcode is not correct.")

    client_limiter.reset(client_key)
    token, token_hash = new_token()
    conn.execute(
        "INSERT INTO sessions (token_hash, profile_id, role, expires_at) VALUES (?,?,?,?)",
        (token_hash, profile["id"], role, session_expiry()),
    )
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (utcnow().isoformat(),))
    log_activity(conn, profile["id"], role, "signed_in", "signed in")
    conn.commit()
    return token, int(profile["id"]), role


__all__ = ["create_profile", "login", "ROLES"]
