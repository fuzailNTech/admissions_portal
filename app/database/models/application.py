import uuid
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Text, Integer, Numeric,
    ForeignKey, Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.database.config.db import Base


# ==================== ENUMS ====================

class ApplicationStatus(str, Enum):
    """Application status throughout the admission process."""
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    DOCUMENTS_PENDING = "documents_pending"
    VERIFIED = "verified"
    OFFERED = "offered"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    WITHDRAWN = "withdrawn"


class VerificationStatus(str, Enum):
    """Verification status for documents and academic records."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ==================== MODELS ====================

class Application(Base):
    """Main application table for student admissions."""
    __tablename__ = "applications"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    
    # Human-readable application number (e.g., "PGC-2026-00001")
    application_number = Column(String(50), unique=True, nullable=False, index=True)
    
    # ==================== STUDENT REFERENCE ====================
    student_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # ==================== APPLICATION TARGET ====================
    institute_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    preferred_campus_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campuses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    program_cycle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("program_admission_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quota_id = Column(
        UUID(as_uuid=True),
        ForeignKey("program_quotas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # ==================== SNAPSHOT LINK ====================
    application_snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("application_snapshots.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    
    # ==================== STATUS & WORKFLOW ====================
    status = Column(
        SQLEnum(ApplicationStatus, name="applicationstatus"),
        nullable=False,
        default="submitted",
        index=True,
    )
    workflow_instance_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_instances.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_to = Column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # ==================== CUSTOM FORM RESPONSES ====================
    custom_form_responses = Column(JSONB, nullable=True)
    # Format: {"form_field_id_1": "answer", "form_field_id_2": "value"}
    
    # ==================== DECISION NOTES ====================
    decision_notes = Column(Text, nullable=True)
    
    # ==================== IMPORTANT DATES ====================
    submitted_at = Column(DateTime(timezone=True), nullable=False)
    last_updated_at = Column(DateTime(timezone=True), nullable=True)
    offer_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # ==================== METADATA ====================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ==================== RELATIONSHIPS ====================
    student_profile = relationship("StudentProfile", foreign_keys=[student_profile_id])
    user = relationship("User", foreign_keys=[user_id])
    institute = relationship("Institute", foreign_keys=[institute_id])
    preferred_campus = relationship("Campus", foreign_keys=[preferred_campus_id])
    program_cycle = relationship("ProgramAdmissionCycle", foreign_keys=[program_cycle_id])
    quota = relationship("ProgramQuota", foreign_keys=[quota_id])
    snapshot = relationship("ApplicationSnapshot", foreign_keys=[application_snapshot_id], uselist=False)
    workflow_instance = relationship("WorkflowInstance", foreign_keys=[workflow_instance_id])
    assigned_staff = relationship("StaffProfile", foreign_keys=[assigned_to])
    
    documents = relationship("ApplicationDocument", back_populates="application", cascade="all, delete-orphan")
    staff_comments = relationship("ApplicationComment", back_populates="application", cascade="all, delete-orphan")
    student_comments = relationship("StudentComment", back_populates="application", cascade="all, delete-orphan")
    status_history = relationship("ApplicationStatusHistory", back_populates="application", cascade="all, delete-orphan")
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index('ix_application_number', 'application_number'),
        Index('ix_application_student_status', 'student_profile_id', 'status'),
        Index('ix_application_institute_campus_program', 'institute_id', 'preferred_campus_id', 'program_cycle_id'),
        Index('ix_application_status_submitted', 'status', 'submitted_at'),
        Index('ix_application_assigned', 'assigned_to', 'status'),
    )


class ApplicationSnapshot(Base):
    """Immutable snapshot of student profile at time of application submission."""
    __tablename__ = "application_snapshots"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    
    # ==================== SNAPSHOT METADATA ====================
    snapshot_created_at = Column(DateTime(timezone=True), nullable=False)
    source_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # ==================== COPY OF STUDENT PROFILE DATA ====================
    # Personal Information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    father_name = Column(String(100), nullable=False)
    
    gender = Column(String(20), nullable=False)  # Store as string for immutability
    date_of_birth = Column(Date, nullable=False)
    
    identity_doc_number = Column(String(15), nullable=False)
    identity_doc_type = Column(String(20), nullable=False)
    
    religion = Column(String(50), nullable=True)
    nationality = Column(String(50), nullable=False)
    
    is_disabled = Column(Boolean, nullable=False)
    disability_details = Column(Text, nullable=True)
    
    # Contact Information
    primary_email = Column(String(255), nullable=False)
    primary_phone = Column(String(20), nullable=False)
    alternate_phone = Column(String(20), nullable=True)
    
    # Address
    street_address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    province = Column(String(50), nullable=False)
    postal_code = Column(String(10), nullable=True)
    
    domicile_province = Column(String(50), nullable=False)
    domicile_district = Column(String(100), nullable=False)
    
    # Documents (S3 URLs - application-specific copies)
    profile_picture_url = Column(String(500), nullable=False)
    identity_doc_url = Column(String(500), nullable=False)
    
    # ==================== METADATA ====================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # ==================== RELATIONSHIPS ====================
    source_profile = relationship("StudentProfile", foreign_keys=[source_profile_id])
    guardians = relationship("ApplicationGuardianSnapshot", back_populates="snapshot", cascade="all, delete-orphan")
    academic_records = relationship("ApplicationAcademicSnapshot", back_populates="snapshot", cascade="all, delete-orphan")
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index('ix_snapshot_source_profile', 'source_profile_id'),
        Index('ix_snapshot_created', 'snapshot_created_at'),
    )


class ApplicationGuardianSnapshot(Base):
    """Immutable snapshot of guardian information."""
    __tablename__ = "application_guardian_snapshots"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    
    application_snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("application_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    source_guardian_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_guardians.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # ==================== COPY OF GUARDIAN DATA ====================
    relationship = Column(String(50), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    
    cnic = Column(String(15), nullable=True)
    phone_number = Column(String(20), nullable=False)
    email = Column(String(255), nullable=True)
    occupation = Column(String(100), nullable=True)
    
    is_primary = Column(Boolean, default=False, nullable=False)
    
    # ==================== METADATA ====================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # ==================== RELATIONSHIPS ====================
    snapshot = relationship("ApplicationSnapshot", back_populates="guardians")
    source_guardian = relationship("StudentGuardian", foreign_keys=[source_guardian_id])
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index('ix_guardian_snapshot_id', 'application_snapshot_id'),
    )


class ApplicationAcademicSnapshot(Base):
    """Immutable snapshot of academic records with per-application verification."""
    __tablename__ = "application_academic_snapshots"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    
    application_snapshot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("application_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    source_academic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_academic_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # ==================== COPY OF ACADEMIC DATA ====================
    level = Column(String(50), nullable=False)
    education_group = Column(String(50), nullable=True)
    
    institute_name = Column(String(255), nullable=False)
    board_name = Column(String(100), nullable=False)
    roll_number = Column(String(50), nullable=False)
    year_of_passing = Column(Integer, nullable=False)
    
    total_marks = Column(Integer, nullable=False)
    obtained_marks = Column(Integer, nullable=False)
    grade = Column(String(10), nullable=True)
    
    # Documents (S3 URLs - application-specific copies)
    result_card_url = Column(String(500), nullable=False)
    
    # ==================== VERIFICATION (PER APPLICATION) ====================
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_status = Column(
        SQLEnum(VerificationStatus, name="verificationstatus"),
        default="pending",
        nullable=False,
        index=True,
    )
    verified_by = Column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # ==================== METADATA ====================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # ==================== RELATIONSHIPS ====================
    snapshot = relationship("ApplicationSnapshot", back_populates="academic_records")
    source_academic = relationship("StudentAcademicRecord", foreign_keys=[source_academic_id])
    verifier = relationship("StaffProfile", foreign_keys=[verified_by])
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index('ix_academic_snapshot_id', 'application_snapshot_id'),
        Index('ix_academic_verification_status', 'verification_status'),
    )


class ApplicationDocument(Base):
    """Application-specific documents with request system."""
    __tablename__ = "application_documents"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # ==================== DOCUMENT DETAILS ====================
    document_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # ==================== FILE INFORMATION ====================
    file_url = Column(String(500), nullable=True)
    file_name = Column(String(255), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    # ==================== REQUEST SYSTEM ====================
    is_required = Column(Boolean, default=False, nullable=False)
    requested_by = Column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_at = Column(DateTime(timezone=True), nullable=True)
    
    # ==================== UPLOAD ====================
    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    
    # ==================== VERIFICATION ====================
    verification_status = Column(
        SQLEnum(VerificationStatus, name="verificationstatus"),
        default="pending",
        nullable=False,
        index=True,
    )
    verified_by = Column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    # ==================== METADATA ====================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ==================== RELATIONSHIPS ====================
    application = relationship("Application", back_populates="documents")
    requester = relationship("StaffProfile", foreign_keys=[requested_by])
    uploader = relationship("User", foreign_keys=[uploaded_by])
    verifier = relationship("StaffProfile", foreign_keys=[verified_by])
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index('ix_document_application_id', 'application_id'),
        Index('ix_document_verification_status', 'application_id', 'verification_status'),
    )


class ApplicationComment(Base):
    """Staff comments on applications (can be internal or visible to student)."""
    __tablename__ = "application_comments"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # ==================== COMMENT ====================
    comment_text = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=False, nullable=False)
    
    # ==================== AUTHOR ====================
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("staff_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # ==================== METADATA ====================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ==================== RELATIONSHIPS ====================
    application = relationship("Application", back_populates="staff_comments")
    author = relationship("StaffProfile", foreign_keys=[created_by])
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index('ix_app_comment_application_created', 'application_id', 'created_at'),
        Index('ix_app_comment_internal', 'application_id', 'is_internal'),
    )


class StudentComment(Base):
    """Student comments on their applications."""
    __tablename__ = "student_comments"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # ==================== COMMENT ====================
    comment_text = Column(Text, nullable=False)
    
    # ==================== AUTHOR ====================
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # ==================== METADATA ====================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ==================== RELATIONSHIPS ====================
    application = relationship("Application", back_populates="student_comments")
    author = relationship("User", foreign_keys=[created_by])
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index('ix_student_comment_application_created', 'application_id', 'created_at'),
    )


class ApplicationStatusHistory(Base):
    """Audit trail for application status changes."""
    __tablename__ = "application_status_history"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # ==================== STATUS CHANGE ====================
    from_status = Column(
        SQLEnum(ApplicationStatus, name="applicationstatus"),
        nullable=True,  # Null for first entry
    )
    to_status = Column(
        SQLEnum(ApplicationStatus, name="applicationstatus"),
        nullable=False,
    )
    notes = Column(Text, nullable=True)
    
    # ==================== CHANGED BY ====================
    changed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # Null = system change
    )
    
    # ==================== METADATA ====================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # ==================== RELATIONSHIPS ====================
    application = relationship("Application", back_populates="status_history")
    changer = relationship("User", foreign_keys=[changed_by])
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index('ix_status_history_application_created', 'application_id', 'created_at'),
    )
