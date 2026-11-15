"""AI endpoints: prescription photo -> DRAFT schedule, and weekly family summary."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..clock import to_local
from ..db import get_db
from ..permissions import Session, require
from ..services import adherence, ai

router = APIRouter(prefix="/api/ai")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAGIC = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png", b"RIFF": "image/webp"}


def _sniff(data: bytes) -> str | None:
    return next((mime for magic, mime in MAGIC.items() if data.startswith(magic)), None)


@router.post("/prescription")
async def read_prescription(
    file: UploadFile = File(...), session: Session = Depends(require("use_ai"))
) -> dict[str, Any]:
    """Returns drafts only. Nothing is saved until a person reviews and confirms in the UI."""
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
        return {"ok": False, "message": f"{exc} Please enter the medicines by hand.", "drafts": [], "disclaimer": ai.DISCLAIMER}
    drafts = [
        {"name": m.name, "dose": m.dose or "as prescribed", "times": ai.draft_times(m.times_per_day),
         "instructions": m.instructions, "start_date": start, "stock": 0}
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
    try:
        text = ai.weekly_summary(profile["name"], stats).summary
        return {"summary": text, "source": "ai", "stats": stats, "message": "", "disclaimer": ai.DISCLAIMER}
    except ai.AIUnavailable as exc:
        return {"summary": facts, "source": "facts", "stats": stats,
                "message": f"{exc} Showing a simple summary instead.", "disclaimer": ai.DISCLAIMER}
