"""
auth.routers — HTTP surface for accounts. Thin: validate, delegate, return.

Endpoints that email an OTP (signup, forgot-password, resend-otp, the
change-password request) are `async def` so the non-blocking aiosmtplib send
runs on the event loop rather than tying up a threadpool worker. Endpoints
that only touch the database stay sync `def` — FastAPI already runs those in
a threadpool, consistent with the rest of this codebase.
"""
from fastapi import APIRouter, Depends, Header, status

from auth.deps import get_current_user
from auth.schemas import (
    AuthResponse,
    AvatarRequest,
    ChangePasswordConfirmRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ResendOtpRequest,
    ResetPasswordRequest,
    SignupRequest,
    UserOut,
    VerifyEmailRequest,
)
from auth.services import AuthService
from core.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
service = AuthService()


def _bearer_token(authorization: str) -> str:
    return authorization.split(" ", 1)[1].strip() if " " in authorization else authorization


@router.post("/signup", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest):
    """Create an account and email a 6-digit verification code."""
    return await service.signup(
        payload.full_name, payload.username, payload.email, payload.country, payload.password,
    )


@router.post("/verify-email", response_model=AuthResponse)
def verify_email(payload: VerifyEmailRequest):
    """Confirm the emailed code — activates the account and logs the user in."""
    return service.verify_email(payload.email, payload.otp)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    """Log in with username or email + password."""
    return service.login(payload.identifier, payload.password)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest):
    """Email a password-reset code. The response never reveals if the account exists."""
    return await service.forgot_password(payload.email)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest):
    """Set a new password using the emailed code. All sessions are revoked."""
    return service.reset_password(payload.email, payload.otp, payload.new_password)


@router.post("/resend-otp", response_model=MessageResponse)
async def resend_otp(payload: ResendOtpRequest):
    """Re-send a signup or reset code."""
    return await service.resend_otp(payload.email, payload.purpose)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """The logged-in user's profile."""
    return service.me(user)


@router.post("/avatar", response_model=UserOut)
def set_avatar(payload: AvatarRequest, user: User = Depends(get_current_user)):
    """Save the profile picture's Cloudinary URL (the client uploads the image
    to Cloudinary directly; this endpoint only records where it landed)."""
    return service.set_avatar(user, payload.avatar_url)


@router.post("/change-password/request", response_model=MessageResponse)
async def change_password_request(user: User = Depends(get_current_user)):
    """Send a confirmation code to the LOGGED-IN user's own registered email —
    never to an address the caller supplies, so a stolen session token alone
    can't redirect the code elsewhere."""
    return await service.change_password_request(user)


@router.post("/change-password/confirm", response_model=MessageResponse)
def change_password_confirm(
    payload: ChangePasswordConfirmRequest,
    authorization: str = Header(default=""),
    user: User = Depends(get_current_user),
):
    """Confirm the emailed code and set the new password. The session that
    made this request stays logged in; every other session is revoked."""
    return service.change_password_confirm(
        user, payload.otp, payload.new_password, _bearer_token(authorization),
    )


@router.post("/logout", response_model=MessageResponse)
def logout(authorization: str = Header(default=""), user: User = Depends(get_current_user)):
    """Invalidate the current session token."""
    return service.logout(_bearer_token(authorization))
