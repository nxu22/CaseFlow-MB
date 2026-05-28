"""
Authentication utilities: password hashing and JWT token handling.

Design decisions (interview talking points):
1. Using bcrypt directly instead of passlib — passlib 1.7.4 is unmaintained
   and breaks with bcrypt 5.0 (reads bcrypt.__about__ which no longer exists).
   bcrypt directly is cleaner: one less abstraction layer, no compatibility risk.
2. JWT stateless auth — no server-side session storage needed; the token itself
   carries the user identity, verified by signature.
3. 'sub' (subject) claim holds the user ID — JWT standard claim for the principal.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from config import settings


# ---------- Password hashing ----------

def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for storage. Returns a UTF-8 string for the DB."""
    # bcrypt works on bytes; salt is generated and embedded in the hash automatically.
    password_bytes = plain_password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against the stored hash. Constant-time compare."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ---------- JWT tokens ----------

def create_access_token(subject: str) -> str:
    """
    Create a signed JWT. 'subject' is the user ID (stored in the 'sub' claim).
    'exp' is required by the JWT spec for expiry; jose validates it automatically on decode.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(subject),   # must be a string per JWT spec
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """
    Verify signature + expiry, return the user ID from 'sub'.
    Returns None on any failure (bad signature, expired, malformed) — the caller
    turns that into a 401. We never leak *why* it failed, to avoid helping attackers.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None
