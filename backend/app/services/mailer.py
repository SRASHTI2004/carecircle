"""Email delivery with HTML + plain-text bodies, retries with backoff and a demo outbox.

Every email is recorded in the outbox. Real SMTP is used only when configured; delivery
failures are logged (type only, never credentials or content) and never raise to callers.
"""

from __future__ import annotations

import html
import logging
import smtplib
import sqlite3
import time
from datetime import datetime, timedelta
from email.message import EmailMessage

from ..clock import utcnow
from ..config import get_settings

log = logging.getLogger("carecircle.mailer")

INLINE_ATTEMPTS = 2
INLINE_BACKOFF_SECONDS = 2.0
MAX_ATTEMPTS = 5
RETRY_WINDOW = timedelta(hours=3)
FOOTER = "CareCircle sends reminders only. It is not medical advice; ask a doctor or pharmacist about any concern."

_sleep = time.sleep  # patched in tests


def render_email(elder_name: str, heading: str, message: str, action: str = "Open CareCircle") -> tuple[str, str]:
    """Return (plain text, HTML). HTML uses large text and a single clear call to action."""
    url = get_settings().app_url
    text = f"{heading}\n\nFor: {elder_name}\n\n{message}\n\n{action}: {url}\n\n-- {FOOTER}"
    esc = html.escape
    body = esc(message).replace("\n", "<br>")
    page = (
        '<!doctype html><html lang="en"><body style="margin:0;background:#f3f5f9;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        '<div style="background:#fff;border-radius:12px;padding:24px;border:1px solid #c5ccd8">'
        '<p style="margin:0 0 8px;color:#475467;font-size:16px">CareCircle &middot; for '
        f"<strong>{esc(elder_name)}</strong></p>"
        f'<h1 style="margin:0 0 16px;font-size:26px;line-height:1.3;color:#17202e">{esc(heading)}</h1>'
        f'<p style="font-size:20px;line-height:1.5;color:#17202e;margin:0 0 24px">{body}</p>'
        f'<a href="{esc(url)}" style="display:inline-block;background:#0b5cad;color:#fff;text-decoration:none;'
        f'font-size:20px;font-weight:bold;padding:14px 24px;border-radius:10px">{esc(action)}</a>'
        "</div>"
        f'<p style="color:#475467;font-size:14px;margin-top:16px">{esc(FOOTER)}</p>'
        "</div></body></html>"
    )
    return text, page


def _smtp_send(to_email: str, subject: str, text: str, page: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.from_email, to_email, subject
    msg.set_content(text)
    if page:
        msg.add_alternative(page, subtype="html")
    if s.smtp_port == 465:
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=15) as server:
            if s.smtp_user:
                server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)
        return
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
        if s.smtp_use_tls:
            server.starttls()
        if s.smtp_user:
            server.login(s.smtp_user, s.smtp_password)
        server.send_message(msg)


def _attempt(conn: sqlite3.Connection, row_id: int, tries: int) -> bool:
    """Try to deliver one outbox row up to `tries` times with backoff; record the outcome."""
    row = conn.execute("SELECT * FROM outbox WHERE id = ?", (row_id,)).fetchone()
    if row is None or not get_settings().smtp_configured:
        return False
    error = ""
    for attempt in range(tries):
        try:
            _smtp_send(row["to_email"], row["subject"], row["body"], row["html"])
            conn.execute(
                "UPDATE outbox SET delivered = 1, error = '', attempts = attempts + ?, last_attempt_at = ? WHERE id = ?",
                (attempt + 1, utcnow().isoformat(), row_id),
            )
            return True
        except (OSError, smtplib.SMTPException) as exc:
            error = type(exc).__name__
            log.warning("smtp delivery failed (attempt %d): %s", attempt + 1, error)
            if attempt + 1 < tries:
                _sleep(INLINE_BACKOFF_SECONDS * (attempt + 1))
    conn.execute(
        "UPDATE outbox SET error = ?, attempts = attempts + ?, last_attempt_at = ? WHERE id = ?",
        (error, tries, utcnow().isoformat(), row_id),
    )
    return False


def send_email(
    conn: sqlite3.Connection, profile_id: int, to_email: str, subject: str, text: str, page: str = ""
) -> bool:
    """Record an email and send it if SMTP is configured. Returns True only if actually delivered."""
    cur = conn.execute(
        "INSERT INTO outbox (profile_id, to_email, subject, body, html, created_at) VALUES (?,?,?,?,?,?)",
        (profile_id, to_email, subject, text, page, utcnow().isoformat()),
    )
    return _attempt(conn, int(cur.lastrowid or 0), INLINE_ATTEMPTS)


def retry_failed(conn: sqlite3.Connection, now: datetime | None = None) -> int:
    """Retry recent undelivered emails (backing off 5 min x attempts). Returns how many were delivered."""
    if not get_settings().smtp_configured:
        return 0
    now = now or utcnow()
    delivered = 0
    rows = conn.execute(
        "SELECT id, attempts, last_attempt_at FROM outbox WHERE delivered = 0 AND attempts > 0 AND attempts < ? AND created_at > ?",
        (MAX_ATTEMPTS, (now - RETRY_WINDOW).isoformat()),
    ).fetchall()
    for row in rows:
        last = datetime.fromisoformat(row["last_attempt_at"]) if row["last_attempt_at"] else None
        if last and now - last < timedelta(minutes=5 * row["attempts"]):
            continue
        delivered += int(_attempt(conn, row["id"], 1))
    return delivered
