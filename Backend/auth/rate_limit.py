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
    key = identifier.strip().lower()
    with _lock:
        _failures.pop(key, None)
