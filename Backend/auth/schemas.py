"""
auth.schemas — the auth API contract.
"""
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")


def _clean_email(v: str) -> str:
    v = v.strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("Enter a valid email address.")
    return v


class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=80)
    username: str
    email: str
    country: str = Field(..., min_length=2, max_length=60)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _clean_email(v)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip().lower()
        if not _USERNAME_RE.match(v):
            raise ValueError("Username must be 3-20 characters: letters, numbers, underscore.")
        return v

    @field_validator("full_name", "country")
    @classmethod
    def _trim(cls, v: str) -> str:
        return v.strip()


class VerifyEmailRequest(BaseModel):
    email: str
    otp: str = Field(..., min_length=6, max_length=6)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _clean_email(v)


class LoginRequest(BaseModel):
    identifier: str = Field(..., description="Username or email")
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _clean_email(v)


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _clean_email(v)


class ResendOtpRequest(BaseModel):
    email: str
    purpose: str = Field(..., pattern="^(signup|reset)$")

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _clean_email(v)


class UserOut(BaseModel):
    id: str
    full_name: str
    username: str
    email: str
    country: str
    avatar_url: str = ""
    email_verified: bool
    created_at: str
    last_login_at: Optional[str] = None


class AvatarRequest(BaseModel):
    avatar_url: str = Field(..., max_length=500, description="Cloudinary secure_url, or '' to remove")


class ChangePasswordConfirmRequest(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class MessageResponse(BaseModel):
    message: str
    dev_otp: Optional[str] = Field(
        default=None,
        description="Present ONLY in development when SMTP is unconfigured — never in production.",
    )
