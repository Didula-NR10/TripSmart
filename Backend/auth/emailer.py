from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib
import httpx

from core.config import settings

log = logging.getLogger("trip_smart.auth.emailer")

_SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"

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

def _from_address() -> str:
    return settings.SMTP_FROM_EMAIL or settings.SMTP_USER

def sendgrid_configured() -> bool:
    return bool(settings.SENDGRID_API_KEY and _from_address())

def smtp_configured() -> bool:
    return bool(settings.SMTP_USER and settings.SMTP_APP_PASSWORD)

def _app_password() -> str:
    return settings.SMTP_APP_PASSWORD.replace(" ", "")

async def _send_via_sendgrid(to_email: str, subject: str, body: str) -> bool:
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": _from_address()},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                _SENDGRID_URL,
                json=payload,
                headers={"Authorization": f"Bearer {settings.SENDGRID_API_KEY}"},
            )
        if response.status_code == 202:
            log.info("OTP email sent to %s via SendGrid", to_email)
            return True
        log.error(
            "SendGrid rejected the OTP email to %s: %s %s",
            to_email, response.status_code, response.text[:500],
        )
        return False
    except Exception as e:
        log.error("SendGrid request failed for %s: %s", to_email, e)
        return False

async def _send_via_smtp(to_email: str, subject: str, body: str) -> bool:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _from_address()
    msg["To"] = to_email
    msg.set_content(body)

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
        log.info("OTP email sent to %s via SMTP", to_email)
        return True
    except Exception as e:
        log.error("Failed to send OTP email to %s via SMTP: %s", to_email, e)
        return False

async def send_otp(to_email: str, code: str, purpose: str) -> bool:
    subject = _SUBJECTS.get(purpose, _SUBJECTS["signup"])
    body = _BODIES.get(purpose, _BODIES["signup"]).format(code=code, ttl=settings.OTP_TTL_MINUTES)

    if sendgrid_configured():
        return await _send_via_sendgrid(to_email, subject, body)
    if smtp_configured():
        return await _send_via_smtp(to_email, subject, body)

    log.warning(
        "Email not configured (SENDGRID_API_KEY, or SMTP_USER/SMTP_APP_PASSWORD, are empty) "
        "— OTP not emailed."
    )
    return False
