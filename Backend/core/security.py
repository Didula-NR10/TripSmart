"""
JWT verification. The forecast endpoints are public reads, but history and
admin routes can depend on these.
"""
from datetime import datetime, timedelta

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings

security = HTTPBearer(auto_error=False)


def create_access_token(subject: str, role: str = "user") -> str:
    payload = {
        "sub": subject,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_role(allowed_roles: list[str]):
    """Dependency factory: `Depends(verify_role(["admin"]))`."""

    def dependency(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
        if credentials is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        except jwt.PyJWTError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        if payload.get("role") not in allowed_roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return payload

    return dependency
