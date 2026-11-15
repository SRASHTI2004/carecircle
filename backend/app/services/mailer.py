"""Email delivery. Every email is recorded in the outbox; real SMTP is used only when configured."""
from __future__ import annotations

import logging
import smtplib
import sqlite3
from email.message import EmailMessage

from ..clock import utcnow
from ..config import get_settings

log = logging.getLogger("carecircle.mailer")


def _smtp_send(to_email: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.from_email, to_email, subject
    msg.set_content(body)
    if s.smtp_port == 465:
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=15) as server:
            if s.smtp_user:
                server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
            server.starttls()
            if s.smtp_user:
                server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)


def send_email(conn: sqlite3.Connection, profile_id: int, to_email: str, subject: str, body: str) -> bool:
    """Send (or, without SMTP, only record) an email. Returns True if actually delivered."""
    delivered, error = False, ""
    if get_settings().smtp_configured:
        try:
            _smtp_send(to_email, subject, body)
            delivered = True
        except (OSError, smtplib.SMTPException) as exc:
            error = type(exc).__name__  # never log credentials or message content
            log.warning("SMTP delivery failed: %s", error)
    conn.execute(
        "INSERT INTO outbox (profile_id, to_email, subject, body, delivered, error, created_at) VALUES (?,?,?,?,?,?,?)",
        (profile_id, to_email, subject, body, int(delivered), error, utcnow().isoformat()),
    )
    return delivered
