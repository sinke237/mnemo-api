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
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """
    Hash a plaintext password with bcrypt and return the hash as a UTF-8 string.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
