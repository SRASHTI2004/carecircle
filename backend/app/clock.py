"""Time helpers. Schedules are stored as naive local times in the elder's timezone."""
from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ISO_MINUTES = "%Y-%m-%dT%H:%M"


def utcnow() -> datetime:
    return datetime.now(UTC)


def valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


def to_local(tz_name: str, now_utc: datetime | None = None) -> datetime:
    """Return `now_utc` as a naive datetime in the given timezone."""
    now = now_utc or utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None, second=0, microsecond=0)


def parse_slot(value: str) -> datetime:
    return datetime.strptime(value, ISO_MINUTES)


def fmt_slot(value: datetime) -> str:
    return value.strftime(ISO_MINUTES)
