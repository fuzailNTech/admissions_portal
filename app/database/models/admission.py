import uuid
import enum
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Integer,
    Date,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from app.database.config.db import Base


class AcademicSession(str, enum.Enum):
    """Academic session/year"""
    SPRING = "spring"   # Jan-Jun (less common for intermediate)
    FALL = "fall"       # Aug-Dec (rare for intermediate)
    ANNUAL = "annual"   # Most common for intermediate colleges
    SUMMER = "summer"   # Summer programs


class AdmissionCycleStatus(str, enum.Enum):
    """Status of admission cycle"""
    DRAFT = "draft"          # Being prepared
    UPCOMING = "upcoming"    # Published but not started
    OPEN = "open"            # Applications being accepted
    CLOSED = "closed"        # Applications closed
    COMPLETED = "completed"  # All admissions finalized
    CANCELLED = "cancelled"  # Cycle cancelled


class QuotaType(str, enum.Enum):
    """Types of admission quotas"""
    OPEN_MERIT = "open_merit"
    HAFIZ_E_QURAN = "hafiz_e_quran"
    SPORTS = "sports"
    MINORITY = "minority"
    DISTRICT_RESERVED = "district_reserved"
    SIBLING = "sibling"
    EMPLOYEE_CHILDREN = "employee_children"
    DISABLED = "disabled"
    OVERSEAS_PAKISTANI = "overseas_pakistani"
    DEFENSE_FORCES = "defense_forces"  # Armed forces personnel children
    CUSTOM = "custom"  # For institute-specific quotas


class QuotaStatus(str, enum.Enum):
    """Status of quota"""
    ACTIVE = "active"
    FILLED = "filled"
    SUSPENDED = "suspended"


class AdmissionCycle(Base):
    """Manages admission cycles/calendars for institutes"""
    __tablename__ = "admission_calendars"

    # Core Identity
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )

    # Foreign Keys
    campus_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campuses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Cycle Information
    name = Column(String, nullable=False)  # e.g., "Admissions 2026", "Intermediate 2026-27"
    academic_year = Column(String, nullable=False, index=True)  # e.g., "2026-27", "2026"
    session = Column(SQLEnum(AcademicSession), default=AcademicSession.ANNUAL, nullable=False)
    status = Column(SQLEnum(AdmissionCycleStatus), default=AdmissionCycleStatus.DRAFT, nullable=False, index=True)
    application_start_date = Column(DateTime(timezone=True), nullable=False)
    application_end_date = Column(DateTime(timezone=True), nullable=False)
    description = Column(Text, nullable=True)  # General details about the admission cycle
    custom_metadata = Column(JSONB, default=dict, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)  # Visible to public

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    campus = relationship("Campus", back_populates="admission_calendars")
    programs = relationship("ProgramAdmissionCycle", back_populates="calendar", cascade="all, delete-orphan")

    # Constraints / Indexes
    __table_args__ = (
        Index("ix_calendar_campus_year", "campus_id", "academic_year"),
        Index("ix_calendar_status_published", "status", "is_published"),
    )

    def __repr__(self):
        return f"<AdmissionCycle(name='{self.name}', year='{self.academic_year}', status='{self.status}')>"


class ProgramAdmissionCycle(Base):
    """Junction table: Links programs to calendars with program-specific settings"""
    __tablename__ = "admission_calendar_programs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )

    # Foreign Keys
    admission_cycle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_calendars.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    total_seats = Column(Integer, nullable=False)  # Total seats for this program in this cycle
    seats_filled = Column(Integer, default=0, nullable=False)
    minimum_marks_required = Column(Integer, nullable=True)
    eligibility_criteria = Column(JSONB, default=dict, nullable=False)
    description = Column(Text, nullable=True)  # Program-specific details for this cycle
    custom_metadata = Column(JSONB, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    calendar = relationship("AdmissionCycle", back_populates="programs")
    program = relationship("Program", back_populates="calendar_programs")
    quotas = relationship("ProgramQuota", back_populates="calendar_program", cascade="all, delete-orphan")
    program_form_fields = relationship("ProgramFormField", back_populates="calendar_program", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint("admission_cycle_id", "program_id", name="uq_cycle_program"),
        Index("ix_cycle_program_active", "admission_cycle_id", "is_active"),
    )

    @validates("seats_filled")
    def validate_seats_filled(self, key, value):
        """Ensure seats_filled doesn't exceed total_seats"""
        if value > self.total_seats:
            raise ValueError(f"Seats filled ({value}) cannot exceed total seats ({self.total_seats})")
        return value

    def __repr__(self):
        return f"<ProgramAdmissionCycle(program_id='{self.program_id}', seats={self.seats_filled}/{self.total_seats})>"


class ProgramQuota(Base):
    """Quota breakdown for each program in an admission calendar"""
    __tablename__ = "program_quotas"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )

    # Foreign Key
    program_cycle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_calendar_programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    quota_type = Column(SQLEnum(QuotaType), nullable=False, index=True)
    quota_name = Column(String, nullable=False)  # Display name: "Open Merit", "Hafiz-e-Quran"
    # Seat Allocation
    allocated_seats = Column(Integer, nullable=False)  # Number of seats for this quota
    seats_filled = Column(Integer, default=0, nullable=False)
    # Eligibility & Requirements
    eligibility_requirements = Column(JSONB, default=dict, nullable=False)
    required_documents = Column(JSONB, default=list, nullable=False)
    minimum_marks = Column(Integer, nullable=True)  # Different minimum for different quotas
    # Priority & Status
    priority_order = Column(Integer, default=0, nullable=False)  # For merit list generation order
    status = Column(SQLEnum(QuotaStatus), default=QuotaStatus.ACTIVE, nullable=False)
    # Additional Settings
    description = Column(Text, nullable=True)
    custom_metadata = Column(JSONB, default=dict, nullable=False)  # Flexible for custom rules

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    program_cycle = relationship("ProgramAdmissionCycle", back_populates="quotas")

    # Constraints
    __table_args__ = (
        UniqueConstraint("program_cycle_id", "quota_type", name="uq_program_cycle_quota_type"),
        Index("ix_quota_program_cycle_status", "program_cycle_id", "status"),
    )

    @validates("seats_filled")
    def validate_seats_filled(self, key, value):
        """Ensure seats_filled doesn't exceed allocated_seats"""
        if value > self.allocated_seats:
            raise ValueError(f"Seats filled ({value}) cannot exceed allocated seats ({self.allocated_seats})")
        return value

    def __repr__(self):
        return f"<ProgramQuota(type='{self.quota_type}', seats={self.seats_filled}/{self.allocated_seats})>"


class FieldType(str, enum.Enum):
    """Types of custom form fields"""
    TEXT = "text"          # Single line text
    TEXTAREA = "textarea"  # Multi-line text
    NUMBER = "number"
    EMAIL = "email"
    TEL = "tel"            # Phone number
    DATE = "date"
    SELECT = "select"      # Dropdown
    RADIO = "radio"        # Radio buttons
    CHECKBOX = "checkbox"  # Multiple checkboxes
    FILE = "file"          # File upload


class CustomFormField(Base):
    """Institute-level reusable form field library"""
    __tablename__ = "custom_form_fields"

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
        index=True
    )

    # Field Configuration
    field_name = Column(String, nullable=False, index=True)  # Internal identifier (e.g., "why_premed")
    label = Column(String, nullable=False)  # Display label (e.g., "Why do you want to study Pre-Medical?")
    field_type = Column(SQLEnum(FieldType), nullable=False)

    # Field Properties
    placeholder = Column(String, nullable=True)  # Placeholder text
    help_text = Column(Text, nullable=True)      # Help text below field
    default_value = Column(String, nullable=True)

    # Validation
    min_length = Column(Integer, nullable=True)  # For text fields
    max_length = Column(Integer, nullable=True)  # For text fields
    min_value = Column(Integer, nullable=True)   # For number fields
    max_value = Column(Integer, nullable=True)   # For number fields
    pattern = Column(String, nullable=True)      # Regex pattern for validation

    # Options (for select, radio, checkbox)
    options = Column(JSONB, default=list, nullable=False)

    # Additional Settings
    description = Column(Text, nullable=True)  # Field description for admin
    custom_metadata = Column(JSONB, default=dict, nullable=False)  # Extra configuration

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    institute = relationship("Institute", back_populates="custom_form_fields")
    program_form_fields = relationship("ProgramFormField", back_populates="form_field", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint("institute_id", "field_name", name="uq_institute_field_name"),
        Index("ix_custom_field_institute_name", "institute_id", "field_name"),
    )

    def __repr__(self):
        return f"<CustomFormField(field_name='{self.field_name}', type='{self.field_type}')>"


class ProgramFormField(Base):
    """Junction table: Links custom form fields to program calendars"""
    __tablename__ = "program_form_fields"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )

    # Foreign Keys
    program_cycle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_calendar_programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    form_field_id = Column(
        UUID(as_uuid=True),
        ForeignKey("custom_form_fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Program-specific overrides
    is_required = Column(Boolean, default=False, nullable=False)  # Can override requirement

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    program_cycle = relationship("ProgramAdmissionCycle", back_populates="program_form_fields")
    form_field = relationship("CustomFormField", back_populates="program_form_fields")

    # Constraints
    __table_args__ = (
        UniqueConstraint("program_cycle_id", "form_field_id", name="uq_program_cycle_form_field"),
    )

    def __repr__(self):
        return f"<ProgramFormField(program_cycle_id='{self.program_cycle_id}', field_id='{self.form_field_id}', required={self.is_required})>"
