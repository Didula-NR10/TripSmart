from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import HTTPException, status

from core.config import settings
from core.database import db_available, get_session
from core.models import AuthToken, EmailOtp, User
from auth.emailer import send_otp
from auth.rate_limit import clear as clear_login_failures, record_failure, seconds_until_unlocked
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

    def login(self, identifier: str, password: str) -> dict:
        _require_db()
        ident = identifier.strip().lower()

        wait = seconds_until_unlocked(ident)
        if wait:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Try again in {wait} seconds.",
            )

        with get_session() as session:
            user = session.query(User).filter(
                (User.email == ident) | (User.username == ident)
            ).first()
            if user is None or not verify_password(password, user.password_hash):
                record_failure(ident)
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED, detail="Wrong username/email or password.",
                )
            if not user.email_verified:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    detail="Email not verified. Request a new code and verify first.",
                )
            clear_login_failures(ident)
            user.last_login_at = _now()
            token = _create_session(session, user)
            return {"token": token, "user": _user_out(user)}

    async def login_with_google(self, id_token: str) -> dict:
        _require_db()
        if not settings.GOOGLE_OAUTH_WEB_CLIENT_ID:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google sign-in is not configured (GOOGLE_OAUTH_WEB_CLIENT_ID is empty).",
            )

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo", params={"id_token": id_token}
            )
        if resp.status_code != 200:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid Google ID token.")
        claims = resp.json()

        if claims.get("aud") != settings.GOOGLE_OAUTH_WEB_CLIENT_ID:
            log.warning("Google ID token audience mismatch: got %s", claims.get("aud"))
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid Google ID token.")
        if claims.get("email_verified") not in ("true", True):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, detail="Google account email is not verified.",
            )

        email = claims["email"].strip().lower()
        google_sub = claims["sub"]
        full_name = claims.get("name") or email.split("@")[0]

        with get_session() as session:
            user = (
                session.query(User)
                .filter((User.email == email) | (User.google_sub == google_sub))
                .first()
            )
            if user is None:
                username = self._unique_username(session, email.split("@")[0])
                user = User(
                    full_name=full_name,
                    username=username,
                    email=email,
                    country="",
                    password_hash=hash_password(secrets.token_hex(32)),
                    email_verified=True,
                    google_sub=google_sub,
                )
                session.add(user)
            else:
                user.email_verified = True
                if not user.google_sub:
                    user.google_sub = google_sub
                user.updated_at = _now()

            user.last_login_at = _now()
            session.flush()
            token = _create_session(session, user)
            session.refresh(user)
            return {"token": token, "user": _user_out(user)}

    @staticmethod
    def _unique_username(session, base: str) -> str:
        base = "".join(c for c in base.lower() if c.isalnum() or c == "_")[:16] or "traveller"
        candidate = base
        suffix = 0
        while session.query(User).filter(User.username == candidate).first() is not None:
            suffix += 1
            candidate = f"{base}{suffix}"
        return candidate

    async def forgot_password(self, email: str) -> dict:
        _require_db()
        dev_otp = None
        with get_session() as session:
            user = session.query(User).filter(User.email == email).first()
            code = _issue_otp(session, email, "reset") if user else None

        if code:
            dev_otp = await _deliver(email, code, "reset")

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

            session.query(AuthToken).filter(
                AuthToken.user_id == row.id, AuthToken.token != current_token
            ).delete()
        return {"message": "Password changed.", "dev_otp": None}

    def update_username(self, user: User, new_username: str) -> dict:
        _require_db()
        with get_session() as session:
            clash = session.query(User).filter(
                User.username == new_username, User.id != user.id,
            ).first()
            if clash:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, detail="This username is already taken.",
                )
            row = session.query(User).filter(User.id == user.id).first()
            if row is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Account not found.")
            row.username = new_username
            row.updated_at = _now()
            return _user_out(row)

    def delete_account(self, user: User) -> dict:
        _require_db()
        with get_session() as session:
            session.query(User).filter(User.id == user.id).delete()
        return {"message": "Account deleted.", "dev_otp": None}

    def set_avatar(self, user: User, avatar_url: str) -> dict:
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

    def logout(self, token: str) -> dict:
        _require_db()
        with get_session() as session:
            session.query(AuthToken).filter(AuthToken.token == token).delete()
        return {"message": "Logged out.", "dev_otp": None}

    def me(self, user: User) -> dict:
        return _user_out(user)
