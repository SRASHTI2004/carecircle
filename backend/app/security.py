"""Passcode hashing, session tokens and login rate limiting."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from datetime import timedelta

import bcrypt

from .clock import utcnow
from .config import get_settings

# Unambiguous characters (no 0/O, 1/I/L) so passcodes are easy to read aloud.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def hash_passcode(passcode: str) -> str:
    rounds = get_settings().bcrypt_rounds
    return bcrypt.hashpw(passcode.encode(), bcrypt.gensalt(rounds)).decode()


def verify_passcode(passcode: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(passcode.encode(), hashed.encode())
    except ValueError:
        return False


def random_code(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def new_passcode(profile_code: str) -> str:
    """Passcodes look like `K7QD-HM4P9XWT`: the public profile code plus a secret."""
    return f"{profile_code}-{random_code(8)}"


def new_token() -> tuple[str, str]:
    """Return (token, sha256 hash). Only the hash is stored."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def session_expiry() -> str:
    return (utcnow() + timedelta(hours=get_settings().session_hours)).isoformat()


class RateLimiter:
    """Fixed-window failed-attempt counter keyed by an arbitrary string."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        hits = [t for t in self._hits.get(key, []) if now - t < self.window]
        if hits:
            self._hits[key] = hits
        else:
            self._hits.pop(key, None)
        return hits

    def retry_after(self, key: str, now: float | None = None) -> int:
        """Seconds until another attempt is allowed (0 if allowed now)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._prune(key, now)
            if len(hits) < self.max_attempts:
                return 0
            return max(1, int(self.window - (now - hits[0])))

    def record_failure(self, key: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            self._prune(key, now)
            self._hits.setdefault(key, []).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


# 5 wrong guesses per client+profile, and 20 per profile overall, per 15 minutes.
FIFTEEN_MINUTES = 15 * 60
ONE_HOUR = 60 * 60
LOGIN_ATTEMPTS_PER_CLIENT = 5
LOGIN_ATTEMPTS_PER_PROFILE = 20
PROFILES_PER_CLIENT_PER_HOUR = 10
AI_CALLS_PER_PROFILE_PER_HOUR = 10
TEST_EMAILS_PER_PROFILE_PER_HOUR = 5

client_limiter = RateLimiter(max_attempts=LOGIN_ATTEMPTS_PER_CLIENT, window_seconds=FIFTEEN_MINUTES)
profile_limiter = RateLimiter(max_attempts=LOGIN_ATTEMPTS_PER_PROFILE, window_seconds=FIFTEEN_MINUTES)
create_limiter = RateLimiter(max_attempts=PROFILES_PER_CLIENT_PER_HOUR, window_seconds=ONE_HOUR)
ai_limiter = RateLimiter(max_attempts=AI_CALLS_PER_PROFILE_PER_HOUR, window_seconds=ONE_HOUR)
email_limiter = RateLimiter(max_attempts=TEST_EMAILS_PER_PROFILE_PER_HOUR, window_seconds=ONE_HOUR)
