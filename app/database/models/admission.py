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
    SPRING = "SPRING"   # Jan-Jun (less common for intermediate)
    FALL = "FALL"       # Aug-Dec (rare for intermediate)
    ANNUAL = "ANNUAL"   # Most common for intermediate colleges
    SUMMER = "SUMMER"   # Summer programs


class AdmissionCycleStatus(str, enum.Enum):
    """Status of admission cycle"""
    DRAFT = "DRAFT"          # Being prepared
    UPCOMING = "UPCOMING"    # Published but not started
    OPEN = "OPEN"            # Applications being accepted
    CLOSED = "CLOSED"        # Applications closed
    COMPLETED = "COMPLETED"  # All admissions finalized
    CANCELLED = "CANCELLED"  # Cycle cancelled


class QuotaType(str, enum.Enum):
    """Types of admission quotas"""
    OPEN_MERIT = "OPEN_MERIT"
    HAFIZ_E_QURAN = "HAFIZ_E_QURAN"
    SPORTS = "SPORTS"
    MINORITY = "MINORITY"
    DISTRICT_RESERVED = "DISTRICT_RESERVED"
    SIBLING = "SIBLING"
    EMPLOYEE_CHILDREN = "EMPLOYEE_CHILDREN"
    DISABLED = "DISABLED"
    OVERSEAS_PAKISTANI = "OVERSEAS_PAKISTANI"
    DEFENSE_FORCES = "DEFENSE_FORCES"  # Armed forces personnel children
    CUSTOM = "CUSTOM"  # For institute-specific quotas


class QuotaStatus(str, enum.Enum):
    """Status of quota"""
    ACTIVE = "ACTIVE"
    FILLED = "FILLED"
    SUSPENDED = "SUSPENDED"


class AdmissionCycle(Base):
    """Institute-wide admission cycles/calendars"""
    __tablename__ = "admission_cycles"

    # Core Identity
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )

    # Foreign Keys
    institute_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Cycle Information
    name = Column(String, nullable=False)  # e.g., "Admissions 2026", "Intermediate 2026-27"
    academic_year = Column(String, nullable=False, index=True)  # e.g., "2026-27", "2026"
    session = Column(SQLEnum(AcademicSession), default=AcademicSession.ANNUAL, nullable=False)
    status = Column(SQLEnum(AdmissionCycleStatus), default=AdmissionCycleStatus.DRAFT, nullable=False, index=True)
    
    # Institute-wide dates (apply to all campuses by default)
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
    institute = relationship("Institute", back_populates="admission_cycles")
    campus_cycles = relationship("CampusAdmissionCycle", back_populates="admission_cycle", cascade="all, delete-orphan")

    # Constraints / Indexes
    __table_args__ = (
        Index("ix_cycle_institute_year", "institute_id", "academic_year"),
        Index("ix_cycle_status_published", "status", "is_published"),
    )

    def __repr__(self):
        return f"<AdmissionCycle(name='{self.name}', year='{self.academic_year}', status='{self.status}')>"


class CampusAdmissionCycle(Base):
    """Junction table: Links campuses to admission cycles with campus-specific controls"""
    __tablename__ = "campus_admission_cycles"

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
    admission_cycle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Campus-specific controls
    is_open = Column(Boolean, default=True, nullable=False)  # Can close campus independently
    closure_reason = Column(String, nullable=True)  # Why is this campus closed? (e.g., "Capacity reached", "Emergency")
    
    # Flexible metadata for campus-specific settings
    custom_metadata = Column(JSONB, default=dict, nullable=False)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    campus = relationship("Campus", back_populates="campus_admission_cycles")
    admission_cycle = relationship("AdmissionCycle", back_populates="campus_cycles")
    program_cycles = relationship("ProgramAdmissionCycle", back_populates="campus_admission_cycle", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint("campus_id", "admission_cycle_id", name="uq_campus_admission_cycle"),
        Index("ix_campus_cycle", "campus_id", "admission_cycle_id"),
    )

    def __repr__(self):
        return f"<CampusAdmissionCycle(campus_id='{self.campus_id}', cycle_id='{self.admission_cycle_id}', is_open={self.is_open})>"


class ProgramAdmissionCycle(Base):
    """Program offerings for a specific cycle at a specific campus (seat allocation)"""
    __tablename__ = "program_admission_cycles"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )

    # Foreign Keys
    campus_admission_cycle_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campus_admission_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Seat Allocation
    total_seats = Column(Integer, nullable=False)  # Total seats for this program at this campus for this cycle
    seats_filled = Column(Integer, default=0, nullable=False)
    
    # Details
    description = Column(Text, nullable=True)  # Program-specific details for this cycle
    custom_metadata = Column(JSONB, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    campus_admission_cycle = relationship("CampusAdmissionCycle", back_populates="program_cycles")
    program = relationship("Program", back_populates="program_admission_cycles")
    quotas = relationship("ProgramQuota", back_populates="program_cycle", cascade="all, delete-orphan")

    # Helper properties for easier access
    @property
    def admission_cycle_id(self):
        """Get admission_cycle_id through the campus_admission_cycle relationship"""
        return self.campus_admission_cycle.admission_cycle_id if self.campus_admission_cycle else None
    
    @property
    def campus_id(self):
        """Get campus_id through the campus_admission_cycle relationship"""
        return self.campus_admission_cycle.campus_id if self.campus_admission_cycle else None
    
    @property
    def admission_cycle(self):
        """Get admission_cycle through the campus_admission_cycle relationship"""
        return self.campus_admission_cycle.admission_cycle if self.campus_admission_cycle else None
    
    @property
    def campus(self):
        """Get campus through the campus_admission_cycle relationship"""
        return self.campus_admission_cycle.campus if self.campus_admission_cycle else None

    # Constraints
    __table_args__ = (
        UniqueConstraint("campus_admission_cycle_id", "program_id", name="uq_campus_cycle_program"),
        Index("ix_campus_cycle_program_active", "campus_admission_cycle_id", "program_id", "is_active"),
    )

    @validates("seats_filled")
    def validate_seats_filled(self, key, value):
        """Ensure seats_filled doesn't exceed total_seats"""
        if value > self.total_seats:
            raise ValueError(f"Seats filled ({value}) cannot exceed total seats ({self.total_seats})")
        return value

    def __repr__(self):
        return f"<ProgramAdmissionCycle(campus_cycle='{self.campus_admission_cycle_id}', program='{self.program_id}', seats={self.seats_filled}/{self.total_seats})>"


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
        ForeignKey("program_admission_cycles.id", ondelete="CASCADE"),  
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
    TEXT = "TEXT"          # Single line text
    TEXTAREA = "TEXTAREA"  # Multi-line text
    NUMBER = "NUMBER"
    EMAIL = "EMAIL"
    TEL = "TEL"            # Phone number
    DATE = "DATE"
    SELECT = "SELECT"      # Dropdown
    RADIO = "RADIO"        # Radio buttons
    CHECKBOX = "CHECKBOX"  # Multiple checkboxes
    FILE = "FILE"          # File upload


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
    """Junction table: Links custom form fields to programs (institute-level)"""
    __tablename__ = "program_form_fields"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )

    # Foreign Keys
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    form_field_id = Column(
        UUID(as_uuid=True),
        ForeignKey("custom_form_fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Field Settings
    is_required = Column(Boolean, default=False, nullable=False)
    display_order = Column(Integer, default=0, nullable=False)  # For ordering fields in forms

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    program = relationship("Program", back_populates="program_form_fields")
    form_field = relationship("CustomFormField", back_populates="program_form_fields")

    # Constraints
    __table_args__ = (
        UniqueConstraint("program_id", "form_field_id", name="uq_program_form_field"),
        Index("ix_program_field", "program_id", "form_field_id"),
    )

    def __repr__(self):
        return f"<ProgramFormField(program_id='{self.program_id}', field_id='{self.form_field_id}', required={self.is_required})>"
