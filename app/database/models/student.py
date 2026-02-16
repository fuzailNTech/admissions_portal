import uuid
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Text, Integer, Numeric,
    ForeignKey, Enum as SQLEnum, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.database.config.db import Base


# ==================== ENUMS ====================

class GenderType(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class IdentityDocumentType(str, Enum):
    CNIC = "CNIC"  # Computerized National Identity Card (18+)
    B_FORM = "B_FORM"  # Birth Certificate / Form-B (under 18)


class ReligionType(str, Enum):
    ISLAM = "ISLAM"
    CHRISTIANITY = "CHRISTIANITY"
    HINDUISM = "HINDUISM"
    SIKHISM = "SIKHISM"
    OTHER = "OTHER"


class ProvinceType(str, Enum):
    PUNJAB = "PUNJAB"
    SINDH = "SINDH"
    KPK = "KPK"
    BALOCHISTAN = "BALOCHISTAN"
    GILGIT_BALTISTAN = "GILGIT_BALTISTAN"
    AJK = "AJK"
    ICT = "ICT"
    FATA = "FATA"  # Historically, now merged with KPK


class GuardianRelationship(str, Enum):
    FATHER = "FATHER"
    MOTHER = "MOTHER"
    BROTHER = "BROTHER"
    SISTER = "SISTER"
    UNCLE = "UNCLE"
    AUNT = "AUNT"
    GRANDFATHER = "GRANDFATHER"
    GRANDMOTHER = "GRANDMOTHER"
    LEGAL_GUARDIAN = "LEGAL_GUARDIAN"
    OTHER = "OTHER"


class AcademicLevel(str, Enum):
    PRIMARY = "PRIMARY"
    MIDDLE = "MIDDLE"
    SECONDARY = "SECONDARY"  # SSC / Matric
    HIGHER_SECONDARY = "HIGHER_SECONDARY"  # HSSC / Intermediate


class EducationGroup(str, Enum):
    # ===== SSC LEVEL (Secondary / Matric) =====
    SSC_SCIENCE_BIOLOGY = "SSC_SCIENCE_BIOLOGY"
    SSC_SCIENCE_COMPUTER = "SSC_SCIENCE_COMPUTER"
    SSC_HUMANITIES = "SSC_HUMANITIES"
    SSC_COMMERCE = "SSC_COMMERCE"
    SSC_TECHNICAL = "SSC_TECHNICAL"
    SSC_AGRICULTURE = "SSC_AGRICULTURE"
    SSC_HEALTH_SCIENCE = "SSC_HEALTH_SCIENCE"
    
    # ===== HSSC LEVEL (Higher Secondary / Intermediate) =====
    HSSC_FSC_PRE_MEDICAL = "HSSC_FSC_PRE_MEDICAL"
    HSSC_FSC_PRE_ENGINEERING = "HSSC_FSC_PRE_ENGINEERING"
    HSSC_FSC_GENERAL_SCIENCE = "HSSC_FSC_GENERAL_SCIENCE"
    HSSC_ICS = "HSSC_ICS"
    HSSC_FA = "HSSC_FA"
    HSSC_ICOM = "HSSC_ICOM"
    HSSC_DCOM = "HSSC_DCOM"
    HSSC_TECHNICAL = "HSSC_TECHNICAL"


# ==================== MODELS ====================

class StudentProfile(Base):
    """Student profile containing personal information and universal documents."""
    __tablename__ = "student_profiles"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    
    # ==================== PERSONAL INFORMATION ====================
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    father_name = Column(String(100), nullable=False)  # Pakistani standard
    
    gender = Column(SQLEnum(GenderType, name="gendertype"), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    
    # Identity (Pakistani system)
    identity_doc_number = Column(String(15), unique=True, nullable=False, index=True)
    # Format: XXXXX-XXXXXXX-X (13 digits with dashes)
    identity_doc_type = Column(
        SQLEnum(IdentityDocumentType, name="identitydocumenttype"),
        nullable=False
    )
    
    religion = Column(SQLEnum(ReligionType, name="religiontype"), nullable=True)
    nationality = Column(String(50), default="Pakistani", nullable=False)
    
    # Disability information
    is_disabled = Column(Boolean, default=False, nullable=False)
    disability_details = Column(Text, nullable=True)
    
    # ==================== CONTACT INFORMATION ====================
    primary_email = Column(String(255), nullable=False, index=True)
    primary_phone = Column(String(20), nullable=False)  # Format: +92XXXXXXXXXX
    alternate_phone = Column(String(20), nullable=True)
    
    # ==================== ADDRESS ====================
    street_address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=False)
    province = Column(SQLEnum(ProvinceType, name="provincetype"), nullable=False, index=True)
    postal_code = Column(String(10), nullable=True)
    
    # Domicile (for quota allocation - critical in Pakistan)
    domicile_province = Column(
        SQLEnum(ProvinceType, name="provincetype"),
        nullable=False,
        index=True
    )
    domicile_district = Column(String(100), nullable=False)
    
    # ==================== DOCUMENTS (S3 URLs) ====================
    # Universal documents only
    profile_picture_url = Column(String(500), nullable=False)
    identity_doc_url = Column(String(500), nullable=False)
    
    # ==================== METADATA ====================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ==================== RELATIONSHIPS ====================
    user = relationship("User", foreign_keys=[user_id], back_populates="student_profile")
    guardians = relationship(
        "StudentGuardian",
        back_populates="student_profile",
        cascade="all, delete-orphan"
    )
    academic_records = relationship(
        "StudentAcademicRecord",
        back_populates="student_profile",
        cascade="all, delete-orphan"
    )
    
    # ==================== INDEXES ====================
    __table_args__ = (
        Index('ix_student_profile_user_id', 'user_id'),
        Index('ix_student_profile_cnic', 'identity_doc_number'),
        Index('ix_student_profile_location', 'city', 'province'),
        Index('ix_student_profile_domicile', 'domicile_province', 'domicile_district'),
    )


class StudentGuardian(Base):
    """Guardian/parent information for students."""
    __tablename__ = "student_guardians"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    student_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # ==================== GUARDIAN INFORMATION ====================
    guardian_relationship = Column(
        SQLEnum(GuardianRelationship, name="guardianrelationship"),
        nullable=False
    )
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    
    cnic = Column(String(15), nullable=True)  # Optional (some families don't share)
    phone_number = Column(String(20), nullable=False)
    email = Column(String(255), nullable=True)
    occupation = Column(String(100), nullable=True)
    
    is_primary = Column(Boolean, default=False, nullable=False)
    # Only one guardian can be primary contact
    
    # ==================== METADATA ====================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ==================== RELATIONSHIPS ====================
    student_profile = relationship("StudentProfile", back_populates="guardians")
    
    # ==================== CONSTRAINTS ====================
    __table_args__ = (
        # If CNIC provided, it must be unique per student
        UniqueConstraint(
            'student_profile_id', 'cnic',
            name='uq_guardian_student_cnic',
        ),
        Index('ix_guardian_student_id', 'student_profile_id'),
    )


class StudentAcademicRecord(Base):
    """Academic records and qualifications for students."""
    __tablename__ = "student_academic_records"
    
    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    student_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # ==================== ACADEMIC DETAILS ====================
    level = Column(SQLEnum(AcademicLevel, name="academiclevel"), nullable=False)
    # PRIMARY, MIDDLE, SECONDARY, HIGHER_SECONDARY
    
    # Education Group (Pakistani system)
    education_group = Column(
        SQLEnum(EducationGroup, name="educationgroup"),
        nullable=True
    )
    # Required for SECONDARY and HIGHER_SECONDARY
    # Null for PRIMARY and MIDDLE
    
    institute_name = Column(String(255), nullable=False)
    board_name = Column(String(100), nullable=False)
    # Examples: BISE Lahore, BISE Rawalpindi, Federal Board, etc.
    
    roll_number = Column(String(50), nullable=False)
    year_of_passing = Column(Integer, nullable=False)
    
    # ==================== MARKS ====================
    total_marks = Column(Integer, nullable=False)
    obtained_marks = Column(Integer, nullable=False)
    
    grade = Column(String(10), nullable=True)
    # A+, A, B, C, etc. (Pakistani grading system)
    
    # ==================== DOCUMENTS (S3 URLs) ====================
    result_card_url = Column(String(500), nullable=False)
    
    # ==================== METADATA ====================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ==================== RELATIONSHIPS ====================
    student_profile = relationship("StudentProfile", back_populates="academic_records")
    
    # ==================== CONSTRAINTS ====================
    __table_args__ = (
        # One record per level/board/roll combination
        UniqueConstraint(
            'student_profile_id', 'level', 'board_name', 'roll_number',
            name='uq_academic_record'
        ),
        Index('ix_academic_student_id', 'student_profile_id'),
        CheckConstraint('obtained_marks <= total_marks', name='check_marks_valid'),
    )
