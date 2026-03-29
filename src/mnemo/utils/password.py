"""
Password hashing utilities.

Uses bcrypt directly to avoid passlib 1.7.4 incompatibility with bcrypt ≥ 4.x
(passlib's detect_wrap_bug test sends a 73-byte probe that bcrypt 4+ rejects).
"""

import bcrypt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a bcrypt hash.
    """
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed/corrupted hash or wrong type — treat as authentication failure
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a plaintext password with bcrypt and return the hash as a UTF-8 string.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# A dummy bcrypt hash used to equalize authentication timing when a user
# record does not exist or has no password. Generated at import time so it's
# a valid bcrypt-formatted hash compatible with `verify_password`.
DUMMY_PASSWORD_HASH: str = bcrypt.hashpw(b"dummy_password_for_timing", bcrypt.gensalt()).decode(
    "utf-8"
)
