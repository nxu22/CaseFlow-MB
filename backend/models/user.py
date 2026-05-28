"""
User model: law firm staff (lawyers and paralegals) who use the system.

Note: clients (drivers/defendants) are NOT users. They don't log in.
They are stored separately in the clients table.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID

from database import Base


class UserRole(str, enum.Enum):
    """Roles within a law firm. Determines permissions (future extension)."""
    LAWYER = "lawyer"
    PARALEGAL = "paralegal"


class User(Base):
    __tablename__ = "users"

    # UUID primary key: avoids exposing business volume via sequential IDs,
    # and prevents IDOR attacks where attackers guess /users/42.
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Indexed and unique: login lookups by email must be fast,
    # and duplicate accounts must be rejected at DB level.
    email = Column(String(255), unique=True, nullable=False, index=True)

    # Store bcrypt hash, never plaintext. Field name makes intent explicit.
    hashed_password = Column(String(255), nullable=False)

    full_name = Column(String(255), nullable=False)

    role = Column(
        Enum(UserRole, name="user_role_enum"),
        nullable=False,
        default=UserRole.PARALEGAL,
    )

    # Soft delete flag: deactivated users keep their historical case assignments
    # intact. Hard deletion would orphan cases.
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"
