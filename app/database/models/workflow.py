import uuid
from sqlalchemy import Column, String, Boolean, DateTime, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database.config.db import Base


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
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    business_key = Column(String, index=True)
    definition = Column(String, nullable=False)  # e.g. "user_registration"
    state = Column(LargeBinary, nullable=False)  # pickled workflow state
    created_at = Column(DateTime(timezone=True), server_default=func.now())
