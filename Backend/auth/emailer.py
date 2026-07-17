"""
auth.emailer — sends OTP codes over SMTP, asynchronously (aiosmtplib).

Configured with SMTP_USER + SMTP_APP_PASSWORD in .env — for Gmail this is an
App Password (Google Account → Security → 2-Step Verification → App passwords),
never the real account password; copy-pasted app passwords often carry spaces
("abcd efgh ijkl mnop"), which are stripped before use. Returns False instead
of raising when SMTP is unconfigured or fails, so development without
credentials still works: the service layer then exposes the code in the API
response in development mode.
"""
from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from core.config import settings

log = logging.getLogger("trip_smart.auth.emailer")

_SUBJECTS = {
    "signup": "Your Tripsmart verification code",
    "reset": "Your Tripsmart password reset code",
    "change": "Your Tripsmart password change code",
}

_BODIES = {
    "signup": (
        "Welcome to Tripsmart!\n\n"
        "Your email verification code is: {code}\n\n"
        "It expires in {ttl} minutes. If you didn't create an account, ignore this email."
    ),
    "reset": (
        "A password reset was requested for your Tripsmart account.\n\n"
        "Your reset code is: {code}\n\n"
        "It expires in {ttl} minutes. If you didn't request this, your account is safe — "
        "just ignore this email."
    ),
    "change": (
        "A password change was requested from inside your Tripsmart account.\n\n"
        "Your confirmation code is: {code}\n\n"
        "It expires in {ttl} minutes. If you didn't request this, ignore this email and "
        "consider changing your password — someone may have your session."
    ),
}


def _app_password() -> str:
    # Gmail's UI displays app passwords with spaces for readability; SMTP
    # login needs them removed.
    return settings.SMTP_APP_PASSWORD.replace(" ", "")


def smtp_configured() -> bool:
    return bool(settings.SMTP_USER and settings.SMTP_APP_PASSWORD)


async def send_otp(to_email: str, code: str, purpose: str) -> bool:
    """Deliver a one-time code. True on success, False when not configured/failed."""
    if not smtp_configured():
        log.warning("SMTP not configured (SMTP_USER / SMTP_APP_PASSWORD empty) — OTP not emailed.")
        return False

    msg = EmailMessage()
    msg["Subject"] = _SUBJECTS.get(purpose, _SUBJECTS["signup"])
    msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    msg["To"] = to_email
    msg.set_content(
        _BODIES.get(purpose, _BODIES["signup"]).format(code=code, ttl=settings.OTP_TTL_MINUTES)
    )

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=_app_password(),
            start_tls=settings.SMTP_PORT != 465,
            use_tls=settings.SMTP_PORT == 465,
            timeout=20,
        )
        log.info("OTP email sent to %s (%s)", to_email, purpose)
        return True
    except Exception as e:  # noqa: BLE001 — any SMTP failure must not 500 the API
        log.error("Failed to send OTP email to %s: %s", to_email, e)
        return False
