"""
Document model: files attached to a case.

The file itself lives in S3 (Day 3). The database stores only metadata
plus the S3 object key. This is the standard pattern: RDBMS for relational
data + queries, object storage for blobs.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database import Base


class DocumentType(str, enum.Enum):
    """Categorizes documents for UI filtering and Claude prompt routing."""
    TICKET = "ticket"               # the original traffic ticket
    COURT_NOTICE = "court_notice"   # hearing notices, summons
    EVIDENCE = "evidence"           # photos, dashcam stills, witness statements
    DEFENSE_LETTER = "defense_letter"  # AI-generated draft letters
    OTHER = "other"


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # CASCADE: deleting the case deletes its documents. Document files have
    # no meaning outside the case context.
    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Original filename as uploaded, for display only.
    filename = Column(String(500), nullable=False)

    # S3 object key, e.g. "cases/{case_id}/{uuid}.pdf".
    # NOT the full S3 URL—we generate presigned URLs on demand for security.
    s3_key = Column(String(500), nullable=False, unique=True)

    file_size = Column(Integer, nullable=False)  # bytes
    mime_type = Column(String(100), nullable=False)

    document_type = Column(
        Enum(DocumentType, name="document_type_enum"),
        nullable=False,
        default=DocumentType.OTHER,
    )

    # Claude-generated per-document summary.
    ai_summary = Column(Text, nullable=True)

    # Audit: who uploaded this file. SET NULL on user deletion (same logic
    # as case.assigned_lawyer_id).
    uploaded_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    case = relationship("Case", back_populates="documents")
    uploaded_by = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Document {self.filename} ({self.document_type.value})>"
