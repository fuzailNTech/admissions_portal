import uuid
from sqlalchemy import Column, String, Boolean, DateTime, LargeBinary, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database.config.db import Base
from datetime import datetime, timedelta


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
