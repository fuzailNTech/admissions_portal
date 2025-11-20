import uuid
import enum
from sqlalchemy import Column, String, Boolean, DateTime, LargeBinary, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.config.db import Base
from datetime import datetime, timedelta


class UserRole(str, enum.Enum):
    """User role enumeration."""

    USER = "user"
    SUPER_ADMIN = "super_admin"


class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    email = Column(String, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    verified = Column(Boolean, default=False)
    role = Column(
        Enum(*[e.value for e in UserRole], name="user_role"),
        nullable=False,
        default=UserRole.USER,
        index=True,
    )
    institute_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    institute = relationship("Institute", back_populates="users")


class VerificationToken(Base):
    __tablename__ = "verification_tokens"
    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workflow_instance_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    token = Column(
        String, unique=True, nullable=False
    )  # store raw token or a hash; see notes below
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.utcnow() + timedelta(hours=24),
    )
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
