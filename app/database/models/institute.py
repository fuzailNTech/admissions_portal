import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Enum as SQLEnum, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.config.db import Base
import enum


class InstituteType(str, enum.Enum):
    """Type of educational institute"""
    GOVERNMENT = "government"
    PRIVATE = "private"
    SEMI_GOVERNMENT = "semi_government"


class InstituteStatus(str, enum.Enum):
    """Current operational status of institute"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_APPROVAL = "pending_approval"


class InstituteLevel(str, enum.Enum):
    """Level of education provided"""
    UNIVERSITY = "university"
    COLLEGE = "college"
    INSTITUTE = "institute"
    SCHOOL = "school"


class CampusType(str, enum.Enum):
    """Type of campus by gender"""
    BOYS = "boys"
    GIRLS = "girls"
    CO_ED = "co_ed"  # Co-educational (both)


class Institute(Base):
    """Institutes/colleges/universities that use the student application portal."""
    __tablename__ = "institutes"

    # Core Identity
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    name = Column(String, nullable=False, index=True)
    institute_code = Column(String, unique=True, nullable=False, index=True)  # For CMS linking
    
    # Classification
    institute_type = Column(SQLEnum(InstituteType), nullable=False, index=True)
    institute_level = Column(SQLEnum(InstituteLevel), nullable=False)
    status = Column(SQLEnum(InstituteStatus), default=InstituteStatus.ACTIVE, nullable=False, index=True)
    
    # Official Information
    registration_number = Column(String, nullable=True)  # HEC/Government registration
    regulatory_body = Column(String, nullable=True)  # e.g., "BISE Lahore" , "HEC", "PEC", "PMDC"
    established_year = Column(Integer, nullable=True)
    
    # Contact Information
    primary_email = Column(String, nullable=True)
    primary_phone = Column(String, nullable=True)
    website_url = Column(String, nullable=True)
    
    # Flexible metadata using JSONB for additional fields
    custom_metadata = Column(JSONB, default={}, nullable=False)  # For custom fields, settings, etc.
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)  # Reference to admin user

    # Relationships
    users = relationship("User", back_populates="institute")
    workflow_definitions = relationship("WorkflowDefinition", back_populates="institute", cascade="all, delete-orphan")
    workflow_instances = relationship("WorkflowInstance", back_populates="institute", cascade="all, delete-orphan")
    campuses = relationship("Campus", back_populates="institute", cascade="all, delete-orphan")
    programs = relationship("Program", back_populates="institute", cascade="all, delete-orphan")
    admission_cycles = relationship("AdmissionCycle", back_populates="institute", cascade="all, delete-orphan")
    custom_form_fields = relationship("CustomFormField", back_populates="institute", cascade="all, delete-orphan")


class Campus(Base):
    """Campus of an institute - programs are offered at campus level"""
    __tablename__ = "campuses"

    # Core Identity
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    
    # Foreign Key
    institute_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Campus Info
    name = Column(String, nullable=False)  # e.g., "Main Campus", "Girls Campus", "North Campus"
    campus_code = Column(String, nullable=True)  # Optional code for the campus
    campus_type = Column(SQLEnum(CampusType), nullable=False, index=True)
    # Location
    country = Column(String, default="Pakistan", nullable=False)
    province_state = Column(String, nullable=True, index=True)
    city = Column(String, nullable=True, index=True)
    postal_code = Column(String, nullable=True)
    address_line = Column(String, nullable=True)
    # Contact
    campus_email = Column(String, nullable=True)
    campus_phone = Column(String, nullable=True)
    
    # Operational Settings
    timezone = Column(String, default="Asia/Karachi", nullable=False)
    
    # Flexible metadata
    custom_metadata = Column(JSONB, default={}, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)
    
    # Relationships
    institute = relationship("Institute", back_populates="campuses")
    campus_programs = relationship("CampusProgram", back_populates="campus", cascade="all, delete-orphan")
    campus_admission_cycles = relationship("CampusAdmissionCycle", back_populates="campus", cascade="all, delete-orphan")


class Program(Base):
    """Programs/degrees offered by an institute"""
    __tablename__ = "programs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    
    # Foreign Key
    institute_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Program Identity
    name = Column(String, nullable=False, index=True)  # e.g., "Pre-Medical", "Pre-Engineering"
    code = Column(String, nullable=False, index=True)  # e.g., "PRE-MED", "PRE-ENG"

    # Classification
    level = Column(String, nullable=False, index=True)  # "Intermediate", "Bachelors", "Masters", "PhD"
    category = Column(String, nullable=True, index=True)  # "Science", "Arts", "Commerce"
    duration_years = Column(Integer, nullable=True)  # Program duration in years

    # Description
    description = Column(String, nullable=True)

    # Flexible custom metadata
    custom_metadata = Column(JSONB, default=dict, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    institute = relationship("Institute", back_populates="programs")
    campus_programs = relationship("CampusProgram", back_populates="program", cascade="all, delete-orphan")
    program_form_fields = relationship("ProgramFormField", back_populates="program", cascade="all, delete-orphan")
    program_admission_cycles = relationship("ProgramAdmissionCycle", back_populates="program")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("institute_id", "code", name="uq_institute_program_code"),
        Index("ix_program_institute_code", "institute_id", "code"),
    )

    def __repr__(self):
        return f"<Program(code='{self.code}', name='{self.name}', institute_id='{self.institute_id}')>"


class CampusProgram(Base):
    """Junction table for many-to-many relationship between Campuses and Programs"""
    __tablename__ = "campus_programs"

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
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Status - program can be active/inactive at campus level
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)
    
    # Relationships
    campus = relationship("Campus", back_populates="campus_programs")
    program = relationship("Program", back_populates="campus_programs")
    
    # Constraints - each program can only be added once per campus
    __table_args__ = (
        UniqueConstraint("campus_id", "program_id", name="uq_campus_program"),
        Index("ix_campus_program", "campus_id", "program_id"),
    )
    
    def __repr__(self):
        return f"<CampusProgram(campus_id='{self.campus_id}', program_id='{self.program_id}')>"