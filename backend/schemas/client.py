"""
Client-related request/response schemas.

Design decisions (interview talking points):
1. ClientCreate vs ClientUpdate: Create requires full_name (a client must have
   a name); Update makes EVERY field Optional so PATCH can send just one field.
2. ClientResponse mirrors the SQLAlchemy model but is an explicit API contract —
   we control exactly what leaves the system, decoupled from the DB schema.
3. from_attributes=True lets Pydantic read straight off the ORM object.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class ClientCreate(BaseModel):
    """Input for creating a client. Only full_name is required."""
    full_name: str = Field(min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    drivers_license: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = None
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    """
    Input for PATCH. Every field Optional so the client can send only what
    changes. full_name still has min_length=1 IF provided (can't blank it out).
    """
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    drivers_license: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = None
    notes: Optional[str] = None


class ClientResponse(BaseModel):
    """Output for any endpoint returning a client."""
    id: uuid.UUID
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    drivers_license: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
