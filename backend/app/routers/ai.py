"""AI endpoints: prescription photo -> DRAFT schedule, and weekly family summary."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..clock import to_local, utcnow
from ..db import get_db
from ..permissions import Session, require
from ..security import ai_limiter
from ..services import adherence, ai

router = APIRouter(prefix="/api/ai")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAGIC = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png", b"RIFF": "image/webp"}


CACHE_TTL = timedelta(hours=6)


def _rate_limit(session: Session) -> None:
    """At most 10 AI calls per profile per hour (protects cost and the API key)."""
    key = str(session.profile_id)
    wait = ai_limiter.retry_after(key)
    if wait:
        raise HTTPException(
            429,
            f"AI is limited to 10 requests an hour. Try again in {wait // 60 + 1} minutes.",
            headers={"Retry-After": str(wait)},
        )
    ai_limiter.record_failure(key)


def _sniff(data: bytes) -> str | None:
    return next((mime for magic, mime in MAGIC.items() if data.startswith(magic)), None)


@router.post("/prescription")
async def read_prescription(
    file: UploadFile = File(...), session: Session = Depends(require("use_ai"))
) -> dict[str, Any]:
    """Returns drafts only. Nothing is saved until a person reviews and confirms in the UI."""
    _rate_limit(session)
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "That photo is too large (limit 5 MB).")
    mime = _sniff(data)
    if mime is None or file.content_type not in MIME_TYPES:
        raise HTTPException(415, "Please upload a JPEG, PNG or WebP photo.")
    start = date.today().isoformat()
    try:
        result = ai.extract_prescription(data, mime)
    except ai.AIUnavailable as exc:
        return {
            "ok": False,
            "message": f"{exc} Please enter the medicines by hand.",
            "drafts": [],
            "disclaimer": ai.DISCLAIMER,
        }
    drafts = [
        {
            "name": m.name,
            "dose": m.dose or "as prescribed",
            "times": ai.draft_times(m.times_per_day),
            "instructions": m.instructions,
            "start_date": start,
            "stock": 0,
        }
        for m in result.medicines
    ]
    msg = "" if drafts else "No medicines were found in that photo. Please enter them by hand."
    return {"ok": bool(drafts), "message": msg, "drafts": drafts, "disclaimer": ai.DISCLAIMER}


@router.get("/weekly-summary")
def weekly_summary(
    conn: sqlite3.Connection = Depends(get_db), session: Session = Depends(require("view"))
) -> dict[str, Any]:
    profile = conn.execute("SELECT name, timezone FROM profiles WHERE id = ?", (session.profile_id,)).fetchone()
    stats = adherence.weekly_stats(conn, session.profile_id, to_local(profile["timezone"]))
    facts = ai.plain_summary(profile["name"], stats)
    if stats["percent"] is None:
        return {"summary": facts, "source": "facts", "stats": stats, "message": "", "disclaimer": ai.DISCLAIMER}
    cache_key = "summary:" + hashlib.sha256(json.dumps([profile["name"], stats], sort_keys=True).encode()).hexdigest()
    cached = conn.execute("SELECT value, created_at FROM ai_cache WHERE key = ?", (cache_key,)).fetchone()
    if cached and utcnow() - datetime.fromisoformat(cached["created_at"]) < CACHE_TTL:
        return {"summary": cached["value"], "source": "ai", "stats": stats, "message": "", "disclaimer": ai.DISCLAIMER}
    try:
        try:
            _rate_limit(session)
        except HTTPException:
            raise ai.AIUnavailable("The hourly AI limit was reached.") from None
        text = ai.weekly_summary(profile["name"], stats).summary
        conn.execute(
            "INSERT OR REPLACE INTO ai_cache (key, value, created_at) VALUES (?,?,?)",
            (cache_key, text, utcnow().isoformat()),
        )
        conn.commit()
        return {"summary": text, "source": "ai", "stats": stats, "message": "", "disclaimer": ai.DISCLAIMER}
    except ai.AIUnavailable as exc:
        return {
            "summary": facts,
            "source": "facts",
            "stats": stats,
            "message": f"{exc} Showing a simple summary instead.",
            "disclaimer": ai.DISCLAIMER,
        }
