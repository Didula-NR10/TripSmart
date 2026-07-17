"""
auth.services — signup, email verification, login, password reset.

All flows follow the same shape: validate → mutate inside one get_session()
unit of work → answer. OTP codes live 10 minutes, allow 5 wrong attempts, and
are deleted the moment they succeed. Passwords exist only as PBKDF2 hashes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status

from core.config import settings
from core.database import db_available, get_session
from core.models import AuthToken, EmailOtp, User
from auth.emailer import send_otp
from auth.security import hash_password, new_otp, new_session_token, verify_password

log = logging.getLogger("trip_smart.auth.service")


def _require_db() -> None:
    if not db_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Accounts need the database; SUPABASE_DB_URL is not configured.",
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_out(user: User) -> dict:
    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "username": user.username,
        "email": user.email,
        "country": user.country,
        "avatar_url": user.avatar_url or "",
        "email_verified": user.email_verified,
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def _issue_otp(session, email: str, purpose: str) -> str:
    """Replace any previous code for (email, purpose) with a fresh one."""
    session.query(EmailOtp).filter(
        EmailOtp.email == email, EmailOtp.purpose == purpose
    ).delete()
    code = new_otp()
    session.add(EmailOtp(
        email=email,
        code=code,
        purpose=purpose,
        expires_at=_now() + timedelta(minutes=settings.OTP_TTL_MINUTES),
    ))
    return code


async def _deliver(email: str, code: str, purpose: str) -> Optional[str]:
    """Email the code. Returns the code itself as `dev_otp` when it could not
    be emailed AND we are in development — so the flow stays testable without
    SMTP credentials. In production an email failure is a hard error."""
    if await send_otp(email, code, purpose):
        return None
    if settings.ENVIRONMENT == "development":
        log.warning("DEV MODE: OTP for %s (%s) is %s", email, purpose, code)
        return code
    raise HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        detail="Could not send the verification email. Try again later.",
    )


def _create_session(session, user: User) -> str:
    token = new_session_token()
    session.add(AuthToken(
        token=token,
        user_id=user.id,
        expires_at=_now() + timedelta(days=settings.SESSION_DAYS),
    ))
    return token


def _check_otp(session, email: str, purpose: str, code: str) -> None:
    """Validate a submitted code or raise. Deletes the code when it matches."""
    otp: Optional[EmailOtp] = (
        session.query(EmailOtp)
        .filter(EmailOtp.email == email, EmailOtp.purpose == purpose)
        .order_by(EmailOtp.created_at.desc())
        .first()
    )
    if otp is None or otp.expires_at < _now():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Code expired or not found. Request a new one.",
        )
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        session.delete(otp)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Too many wrong attempts. Request a new code.",
        )
    if otp.code != code:
        otp.attempts += 1
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Incorrect code.")
    session.delete(otp)


class AuthService:

    # ---- signup + verification ----

    async def signup(self, full_name: str, username: str, email: str, country: str,
                      password: str) -> dict:
        _require_db()
        with get_session() as session:
            by_email = session.query(User).filter(User.email == email).first()
            by_username = session.query(User).filter(User.username == username).first()

            if by_email and by_email.email_verified:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists. Log in instead.",
                )
            if by_username and by_username.email != email:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, detail="This username is already taken.",
                )

            if by_email:
                # Unverified account re-registering: refresh the details.
                by_email.full_name = full_name
                by_email.username = username
                by_email.country = country
                by_email.password_hash = hash_password(password)
                by_email.updated_at = _now()
            else:
                session.add(User(
                    full_name=full_name,
                    username=username,
                    email=email,
                    country=country,
                    password_hash=hash_password(password),
                    email_verified=False,
                ))

            code = _issue_otp(session, email, "signup")

        dev_otp = await _deliver(email, code, "signup")
        return {
            "message": f"Verification code sent to {email}. It expires in "
                       f"{settings.OTP_TTL_MINUTES} minutes.",
            "dev_otp": dev_otp,
        }

    def verify_email(self, email: str, otp: str) -> dict:
        _require_db()
        with get_session() as session:
            _check_otp(session, email, "signup", otp)
            user = session.query(User).filter(User.email == email).first()
            if user is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Account not found.")
            user.email_verified = True
            user.last_login_at = _now()
            user.updated_at = _now()
            token = _create_session(session, user)
            return {"token": token, "user": _user_out(user)}

    # ---- login ----

    def login(self, identifier: str, password: str) -> dict:
        _require_db()
        ident = identifier.strip().lower()
        with get_session() as session:
            user = session.query(User).filter(
                (User.email == ident) | (User.username == ident)
            ).first()
            if user is None or not verify_password(password, user.password_hash):
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED, detail="Wrong username/email or password.",
                )
            if not user.email_verified:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail="Email not verified. Request a new code and verify first.",
                )
            user.last_login_at = _now()
            token = _create_session(session, user)
            return {"token": token, "user": _user_out(user)}

    # ---- password reset ----

    async def forgot_password(self, email: str) -> dict:
        _require_db()
        dev_otp = None
        with get_session() as session:
            user = session.query(User).filter(User.email == email).first()
            code = _issue_otp(session, email, "reset") if user else None

        if code:
            dev_otp = await _deliver(email, code, "reset")

        # The response never reveals whether the account exists.
        return {
            "message": f"If an account exists for {email}, a reset code is on its way.",
            "dev_otp": dev_otp,
        }

    def reset_password(self, email: str, otp: str, new_password: str) -> dict:
        _require_db()
        with get_session() as session:
            _check_otp(session, email, "reset", otp)
            user = session.query(User).filter(User.email == email).first()
            if user is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Account not found.")
            user.password_hash = hash_password(new_password)
            user.updated_at = _now()
            # A password change revokes every open session.
            session.query(AuthToken).filter(AuthToken.user_id == user.id).delete()
        return {"message": "Password changed. Log in with your new password.", "dev_otp": None}

    async def resend_otp(self, email: str, purpose: str) -> dict:
        _require_db()
        with get_session() as session:
            user = session.query(User).filter(User.email == email).first()
            if purpose == "signup" and user and user.email_verified:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, detail="This email is already verified — log in.",
                )
            code = _issue_otp(session, email, purpose) if user else None

        dev_otp = await _deliver(email, code, purpose) if code else None
        return {
            "message": f"If an account exists for {email}, a new code is on its way.",
            "dev_otp": dev_otp,
        }

    # ---- change password (logged in — OTP goes to the account's own email) ----

    async def change_password_request(self, user: User) -> dict:
        _require_db()
        with get_session() as session:
            code = _issue_otp(session, user.email, "change")
        dev_otp = await _deliver(user.email, code, "change")
        return {
            "message": f"Confirmation code sent to {user.email}. It expires in "
                       f"{settings.OTP_TTL_MINUTES} minutes.",
            "dev_otp": dev_otp,
        }

    def change_password_confirm(
        self, user: User, otp: str, new_password: str, current_token: str
    ) -> dict:
        _require_db()
        with get_session() as session:
            _check_otp(session, user.email, "change", otp)
            row = session.query(User).filter(User.id == user.id).first()
            if row is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Account not found.")
            row.password_hash = hash_password(new_password)
            row.updated_at = _now()
            # Keep the session that made this request; revoke every other one.
            session.query(AuthToken).filter(
                AuthToken.user_id == row.id, AuthToken.token != current_token
            ).delete()
        return {"message": "Password changed.", "dev_otp": None}

    # ---- profile ----

    def set_avatar(self, user: User, avatar_url: str) -> dict:
        """Store the Cloudinary URL the client uploaded the picture to."""
        _require_db()
        url = avatar_url.strip()
        if url and not (url.startswith("https://") and "res.cloudinary.com" in url):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="avatar_url must be an https Cloudinary delivery URL.",
            )
        with get_session() as session:
            row = session.query(User).filter(User.id == user.id).first()
            if row is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Account not found.")
            row.avatar_url = url
            row.updated_at = _now()
            return _user_out(row)

    # ---- sessions ----

    def logout(self, token: str) -> dict:
        _require_db()
        with get_session() as session:
            session.query(AuthToken).filter(AuthToken.token == token).delete()
        return {"message": "Logged out.", "dev_otp": None}

    def me(self, user: User) -> dict:
        return _user_out(user)
