"""
auth.rate_limit — a small in-memory guard against login brute-forcing.

Tracks recent failed login attempts per identifier (email/username,
case-folded) in a process-local dict. This deployment runs a single uvicorn
worker with no external cache (see Dockerfile), so in-memory state is
sufficient — a process restart clears it, which is an acceptable trade-off
for a lockout window measured in minutes. If this ever runs multi-worker or
multi-instance, move this to Supabase or Redis instead so the counters are
shared.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from core.config import settings

_lock = threading.Lock()
_failures: dict[str, list[datetime]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _window() -> timedelta:
    return timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)


def seconds_until_unlocked(identifier: str) -> int:
    """0 if `identifier` may attempt a login now; otherwise how many seconds
    remain until the oldest attempt in its rolling window expires."""
    key = identifier.strip().lower()
    cutoff = _now() - _window()
    with _lock:
        attempts = [t for t in _failures.get(key, []) if t > cutoff]
        _failures[key] = attempts
        if len(attempts) < settings.LOGIN_MAX_ATTEMPTS:
            return 0
        remaining = (attempts[0] + _window() - _now()).total_seconds()
        return max(1, int(remaining))


def record_failure(identifier: str) -> None:
    key = identifier.strip().lower()
    with _lock:
        _failures.setdefault(key, []).append(_now())


def clear(identifier: str) -> None:
    """Called on a successful login — a legitimate owner shouldn't stay
    throttled because of earlier failed attempts."""
    key = identifier.strip().lower()
    with _lock:
        _failures.pop(key, None)
