"""Runtime configuration, read from environment variables (and a local .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_path: str
    cors_origins: list[str]
    bcrypt_rounds: int
    session_hours: int
    smtp_use_tls: bool
    app_url: str
    reminder_token: str
    disable_scheduler: bool
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_email: str
    gemini_api_key: str
    gemini_model: str
    default_timezone: str

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.from_email)


def get_settings() -> Settings:
    """Read settings fresh each call so tests can override the environment."""
    env = os.environ.get
    return Settings(
        database_path=env("DATABASE_PATH", str(ROOT / "carecircle.db")),
        cors_origins=[o.strip() for o in env("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()],
        bcrypt_rounds=int(env("BCRYPT_ROUNDS", "12")),
        session_hours=int(env("SESSION_TTL", "24")),
        smtp_use_tls=env("SMTP_USE_TLS", "1") != "0",
        app_url=env("APP_URL", "https://carecircle-d9ia.onrender.com"),
        reminder_token=env("REMINDER_TOKEN", ""),
        disable_scheduler=env("DISABLE_SCHEDULER", "") == "1",
        smtp_host=env("SMTP_HOST", ""),
        smtp_port=int(env("SMTP_PORT", "587")),
        smtp_user=env("SMTP_USER", ""),
        smtp_password=env("SMTP_PASSWORD", ""),
        from_email=env("FROM_EMAIL", ""),
        gemini_api_key=env("GEMINI_API_KEY", ""),
        gemini_model=env("GEMINI_MODEL", "gemini-2.5-flash"),
        default_timezone=env("APP_TIMEZONE", "Asia/Kolkata"),
    )
