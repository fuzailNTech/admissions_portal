import uuid
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.config.db import Base


class Institute(Base):
    """Institutes/colleges/universities that use the student application portal."""
    __tablename__ = "institutes"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    name = Column(String, nullable=False, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)  # URL-friendly identifier
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", back_populates="institute")
    workflow_definitions = relationship("WorkflowDefinition", back_populates="institute", cascade="all, delete-orphan")
    workflow_instances = relationship("WorkflowInstance", back_populates="institute", cascade="all, delete-orphan")

