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
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class IdentityDocumentType(str, Enum):
    CNIC = "cnic"  # Computerized National Identity Card (18+)
    B_FORM = "b_form"  # Birth Certificate / Form-B (under 18)


class ReligionType(str, Enum):
    ISLAM = "islam"
    CHRISTIANITY = "christianity"
    HINDUISM = "hinduism"
    SIKHISM = "sikhism"
    OTHER = "other"


class ProvinceType(str, Enum):
    PUNJAB = "punjab"
    SINDH = "sindh"
    KPK = "khyber_pakhtunkhwa"
    BALOCHISTAN = "balochistan"
    GILGIT_BALTISTAN = "gilgit_baltistan"
    AJK = "azad_jammu_kashmir"
    ICT = "islamabad_capital_territory"
    FATA = "fata"  # Historically, now merged with KPK


class GuardianRelationship(str, Enum):
    FATHER = "father"
    MOTHER = "mother"
    BROTHER = "brother"
    SISTER = "sister"
    UNCLE = "uncle"
    AUNT = "aunt"
    GRANDFATHER = "grandfather"
    GRANDMOTHER = "grandmother"
    LEGAL_GUARDIAN = "legal_guardian"
    OTHER = "other"


class AcademicLevel(str, Enum):
    PRIMARY = "primary"
    MIDDLE = "middle"
    SECONDARY = "secondary"  # SSC / Matric
    HIGHER_SECONDARY = "higher_secondary"  # HSSC / Intermediate


class EducationGroup(str, Enum):
    # ===== SSC LEVEL (Secondary / Matric) =====
    SSC_SCIENCE_BIOLOGY = "ssc_science_biology"
    SSC_SCIENCE_COMPUTER = "ssc_science_computer"
    SSC_HUMANITIES = "ssc_humanities"
    SSC_COMMERCE = "ssc_commerce"
    SSC_TECHNICAL = "ssc_technical"
    SSC_AGRICULTURE = "ssc_agriculture"
    SSC_HEALTH_SCIENCE = "ssc_health_science"
    
    # ===== HSSC LEVEL (Higher Secondary / Intermediate) =====
    HSSC_FSC_PRE_MEDICAL = "hssc_fsc_pre_medical"
    HSSC_FSC_PRE_ENGINEERING = "hssc_fsc_pre_engineering"
    HSSC_FSC_GENERAL_SCIENCE = "hssc_fsc_general_science"
    HSSC_ICS = "hssc_ics"
    HSSC_FA = "hssc_fa"
    HSSC_ICOM = "hssc_icom"
    HSSC_DCOM = "hssc_dcom"
    HSSC_TECHNICAL = "hssc_technical"


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
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # ==================== RELATIONSHIPS ====================
    user = relationship("User", foreign_keys=[user_id], back_populates="student_profile")
    creator = relationship("User", foreign_keys=[created_by])
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
    relationship = Column(
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
