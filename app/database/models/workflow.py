import uuid
from sqlalchemy import (
    Column, String, Boolean, DateTime, LargeBinary, ForeignKey,
    Text, Integer, JSON, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.config.db import Base


class WorkflowCatalog(Base):
    """Catalog of reusable subprocesses/subflows (child processes). 
    This is a general/shared catalog, not tied to any specific institute."""
    __tablename__ = "workflow_catalog"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    subflow_key = Column(String, nullable=False, index=True)  # e.g., "communication.send_email"
    version = Column(Integer, nullable=False, default=1)
    process_id = Column(String, nullable=False)  # BPMN process ID
    bpmn_xml = Column(Text, nullable=False)  # Subprocess BPMN XML
    description = Column(Text, nullable=True)
    published = Column(Boolean, default=False, nullable=False, index=True)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    creator = relationship("User")

    # Constraints
    __table_args__ = (
        UniqueConstraint('subflow_key', 'version', name='uq_catalog_key_version'),
        Index('ix_catalog_key_version', 'subflow_key', 'version'),
    )


class WorkflowDefinition(Base):
    """Published workflow definitions (parent processes compiled from manifests)."""
    __tablename__ = "workflow_definitions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    institute_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    process_id = Column(String, nullable=False)  # BPMN process ID (sanitized from workflow_name)
    workflow_name = Column(String, nullable=False)  # Human-readable name
    version = Column(Integer, nullable=False, default=1)
    manifest_json = Column(JSON, nullable=False)  # Original manifest JSON
    bpmn_xml = Column(Text, nullable=False)  # Compiled BPMN XML
    subprocess_refs = Column(JSON, nullable=True)  # List of referenced subprocesses
    # e.g., [{"subflow_key": "communication.send_email", "version": 1, "calledElement": "..."}]
    published = Column(Boolean, default=False, nullable=False, index=True)
    active = Column(Boolean, default=True, nullable=False)  # Can be unpublished but kept for history
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    institute = relationship("Institute", back_populates="workflow_definitions")
    creator = relationship("User")
    instances = relationship("WorkflowInstance", back_populates="workflow_definition")

    # Constraints
    __table_args__ = (
        UniqueConstraint('institute_id', 'process_id', 'version', name='uq_workflow_def_institute_process_version'),
        Index('ix_workflow_def_institute_process_version', 'institute_id', 'process_id', 'version'),
        Index('ix_workflow_def_institute_published', 'institute_id', 'published', 'active'),
    )


class WorkflowInstance(Base):
    """Running workflow instances."""
    __tablename__ = "workflow_instances"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    institute_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_definition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_definitions.id", ondelete="RESTRICT"),  # Don't delete if instances exist
        nullable=False,
        index=True,
    )
    business_key = Column(String, index=True)  # Application ID, user email, etc.
    definition = Column(String, nullable=False)  # Process ID (denormalized for quick access)
    state = Column(LargeBinary, nullable=False)  # Pickled workflow state
    status = Column(
        String,
        nullable=False,
        default="running",
        index=True,
    )  # running, completed, failed, cancelled, suspended
    current_tasks = Column(JSON, nullable=True)  # List of current waiting/user task IDs
    # e.g., ["CA_Interview", "GW_IfPassed"]
    error_message = Column(Text, nullable=True)  # Error message if status is "failed"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    institute = relationship("Institute", back_populates="workflow_instances")
    workflow_definition = relationship("WorkflowDefinition", back_populates="instances")

    # Constraints
    __table_args__ = (
        Index('ix_workflow_instance_institute_status', 'institute_id', 'status'),
        Index('ix_workflow_instance_business_key', 'institute_id', 'business_key'),
    )
