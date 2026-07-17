"""
auth.deps — FastAPI dependencies for protected endpoints.

`get_current_user` turns `Authorization: Bearer <token>` into a User row or a
401. Endpoints that need login just declare it as a dependency.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Header, HTTPException, status

from core.database import db_available, get_session
from core.models import AuthToken, User


def get_current_user(authorization: Optional[str] = Header(default=None)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Login required. Send Authorization: Bearer <token>.",
        )
    if not db_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Accounts need the database; SUPABASE_DB_URL is not configured.",
        )

    token = authorization.split(" ", 1)[1].strip()
    with get_session() as session:
        row = session.query(AuthToken).filter(AuthToken.token == token).first()
        if row is None or row.expires_at < datetime.now(timezone.utc):
            if row is not None:
                session.delete(row)  # expired tokens are garbage-collected on sight
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, detail="Session expired. Log in again.",
            )
        user = session.query(User).filter(User.id == row.user_id).first()
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists.")
        return user
