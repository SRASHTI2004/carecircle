"""Protected endpoint so an external cron can trigger reminders while a free server sleeps."""
from __future__ import annotations

import hmac
import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException

from ..config import get_settings
from ..db import get_db
from ..services.reminders import run_reminders

router = APIRouter(prefix="/api/reminders")


@router.post("/run")
def run(
    x_reminder_token: str | None = Header(default=None), conn: sqlite3.Connection = Depends(get_db)
) -> dict[str, dict[str, int]]:
    expected = get_settings().reminder_token
    if not expected:
        raise HTTPException(503, "Reminder endpoint is disabled: REMINDER_TOKEN is not configured.")
    if not x_reminder_token or not hmac.compare_digest(x_reminder_token, expected):
        raise HTTPException(401, "Invalid reminder token.")
    return {"sent": run_reminders(conn)}
