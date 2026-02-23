from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime, date

from app.database.models.student import (
    GenderType,
    IdentityDocumentType,
    ReligionType,
    ProvinceType,
    GuardianRelationship,
    AcademicLevel,
    EducationGroup,
)


class StudentUpdatePasswordRequest(BaseModel):
    """Request to update student password (current + new)."""
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class StudentLoginRequest(BaseModel):
    """Student login request (identity document number + password)."""
    identity_doc_number: str = Field(..., min_length=1, description="CNIC or B-Form number")
    password: str = Field(..., min_length=1, description="Password")


class StudentLoginResponse(BaseModel):
    """Student login response."""
    user_id: UUID
    token: str
    last_login: Optional[datetime] = None
    is_temporary_password: bool = False

    class Config:
        from_attributes = True


# ==================== /me response schemas ====================


class StudentProfileMe(BaseModel):
    """Full student profile for /me response."""
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    father_name: str
    gender: GenderType
    date_of_birth: date
    identity_doc_number: str
    identity_doc_type: IdentityDocumentType
    religion: Optional[ReligionType] = None
    nationality: str
    is_disabled: bool
    disability_details: Optional[str] = None
    primary_email: str
    primary_phone: str
    alternate_phone: Optional[str] = None
    street_address: str
    city: str
    district: str
    province: ProvinceType
    postal_code: Optional[str] = None
    domicile_province: ProvinceType
    domicile_district: str
    profile_picture_url: str
    identity_doc_url: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GuardianMe(BaseModel):
    """Guardian in /me response."""
    id: UUID
    student_profile_id: UUID
    guardian_relationship: GuardianRelationship
    first_name: str
    last_name: str
    cnic: Optional[str] = None
    phone_number: str
    email: Optional[str] = None
    occupation: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AcademicRecordMe(BaseModel):
    """Academic record in /me response."""
    id: UUID
    student_profile_id: UUID
    level: AcademicLevel
    education_group: Optional[EducationGroup] = None
    institute_name: str
    board_name: str
    roll_number: str
    year_of_passing: int
    total_marks: int
    obtained_marks: int
    grade: Optional[str] = None
    result_card_url: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StudentMeResponse(BaseModel):
    """Response for GET /me: student profile with guardian and academic record (SECONDARY)."""
    student_profile: StudentProfileMe
    guardian: Optional[GuardianMe] = None
    academic_record: Optional[AcademicRecordMe] = None

    class Config:
        from_attributes = True


# ==================== Update profile (PATCH /me) ====================
# Document fields (profile_picture_url, identity_doc_url, result_card_url) are not included;
# use a separate documents endpoint to update those.


class StudentProfileUpdate(BaseModel):
    """Partial update for student profile. Only provided fields are updated. No document URLs."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    father_name: Optional[str] = Field(None, min_length=1, max_length=100)
    gender: Optional[GenderType] = None
    date_of_birth: Optional[date] = None
    religion: Optional[ReligionType] = None
    nationality: Optional[str] = Field(None, max_length=50)
    is_disabled: Optional[bool] = None
    disability_details: Optional[str] = None
    primary_email: Optional[str] = Field(None, max_length=255)
    primary_phone: Optional[str] = Field(None, min_length=10, max_length=20)
    alternate_phone: Optional[str] = Field(None, min_length=10, max_length=20)
    street_address: Optional[str] = Field(None, min_length=1)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    district: Optional[str] = Field(None, min_length=1, max_length=100)
    province: Optional[ProvinceType] = None
    postal_code: Optional[str] = Field(None, max_length=10)
    domicile_province: Optional[ProvinceType] = None
    domicile_district: Optional[str] = Field(None, min_length=1, max_length=100)


class GuardianUpdate(BaseModel):
    """Partial update for guardian. id is required to identify which guardian; only other provided fields are updated."""
    id: UUID = Field(..., description="ID of the guardian to update (from GET /me)")
    guardian_relationship: Optional[GuardianRelationship] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    cnic: Optional[str] = Field(None, min_length=15, max_length=15)
    phone_number: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    occupation: Optional[str] = Field(None, max_length=100)


class AcademicRecordUpdate(BaseModel):
    """Partial update for academic record. id is required to identify which record; no document URLs."""
    id: UUID = Field(..., description="ID of the academic record to update (from GET /me)")
    level: Optional[AcademicLevel] = None
    education_group: Optional[EducationGroup] = None
    institute_name: Optional[str] = Field(None, min_length=1, max_length=255)
    board_name: Optional[str] = Field(None, min_length=1, max_length=100)
    roll_number: Optional[str] = Field(None, min_length=1, max_length=50)
    year_of_passing: Optional[int] = Field(None, ge=1980, le=2030)
    total_marks: Optional[int] = Field(None, gt=0)
    obtained_marks: Optional[int] = Field(None, gt=0)
    grade: Optional[str] = Field(None, max_length=10)


class StudentMeUpdateRequest(BaseModel):
    """Request body for PATCH /me. Only provided sections are updated. Guardian/academic_record include id to identify which entity to update."""
    student_profile: Optional[StudentProfileUpdate] = None
    guardian: Optional[GuardianUpdate] = None
    academic_record: Optional[AcademicRecordUpdate] = None
