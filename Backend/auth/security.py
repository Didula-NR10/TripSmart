from __future__ import annotations

import hashlib
import hmac
import os
import secrets

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 260_000

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, hash_hex = stored.split("$")
        if algorithm != _ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False

def new_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"

def new_session_token() -> str:
    return secrets.token_hex(32)
