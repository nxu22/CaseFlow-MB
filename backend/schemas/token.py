"""
JWT token schemas.

Token = what we send back on login (the OAuth2 'bearer' convention).
TokenData = the decoded payload we extract from a valid token internally.
"""
import uuid

from pydantic import BaseModel


class Token(BaseModel):
    """Login response. 'bearer' is the standard token_type for JWT."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Internal: the verified identity extracted from a token."""
    user_id: uuid.UUID
