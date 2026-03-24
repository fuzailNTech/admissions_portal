from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Literal, Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, date

# Import enums from models
from app.database.models.application import VerificationStatus
from app.database.models.student import (
    GenderType, IdentityDocumentType, ReligionType, ProvinceType,
    GuardianRelationship, AcademicLevel, EducationGroup
)


# ==================== WORKFLOW-BASED APPLICATION (OLD) ====================

class ApplicationCreate(BaseModel):
    """Schema for creating a new application (workflow-based)."""
    institute_id: UUID = Field(..., description="ID of the institute")
    business_key: Optional[str] = Field(None, description="Optional business key (e.g., application ID, email)")
    initial_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Initial workflow data (will be merged with dummy data if not provided)"
    )


class ApplicationResponse(BaseModel):
    """Schema for application/workflow instance response."""
    id: UUID
    institute_id: UUID
    workflow_definition_id: UUID
    business_key: Optional[str]
    definition: str
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ==================== STUDENT APPLICATION SUBMISSION ====================

class StudentProfileBase(BaseModel):
    """Shared student profile fields (no document URLs)."""
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    father_name: str = Field(..., min_length=1, max_length=100, description="Father's name")
    gender: GenderType = Field(..., description="Gender")
    date_of_birth: date = Field(..., description="Date of birth")
    identity_doc_type: IdentityDocumentType = Field(..., description="Type of identity document (CNIC or B-Form)")
    identity_doc_number: str = Field(..., min_length=15, max_length=15, description="Identity document number (format: XXXXX-XXXXXXX-X)")
    religion: Optional[ReligionType] = Field(None, description="Religion")
    nationality: str = Field(default="Pakistani", max_length=50, description="Nationality")
    is_disabled: bool = Field(default=False, description="Is the student disabled?")
    disability_details: Optional[str] = Field(None, description="Details about disability if applicable")
    primary_email: EmailStr = Field(..., description="Primary email address")
    primary_phone: str = Field(..., min_length=10, max_length=20, description="Primary phone number")
    alternate_phone: Optional[str] = Field(None, min_length=10, max_length=20, description="Alternate phone number")
    street_address: str = Field(..., min_length=1, description="Street address")
    city: str = Field(..., min_length=1, max_length=100, description="City")
    district: str = Field(..., min_length=1, max_length=100, description="District")
    province: ProvinceType = Field(..., description="Province")
    postal_code: Optional[str] = Field(None, max_length=10, description="Postal code")
    domicile_province: ProvinceType = Field(..., description="Domicile province")
    domicile_district: str = Field(..., min_length=1, max_length=100, description="Domicile district")

    @field_validator("identity_doc_number")
    @classmethod
    def validate_identity_doc_format(cls, v: str) -> str:
        if not v or len(v) != 15:
            raise ValueError("Identity document must be 15 characters (format: XXXXX-XXXXXXX-X)")
        parts = v.split("-")
        if len(parts) != 3 or len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
            raise ValueError("Identity document format must be: XXXXX-XXXXXXX-X")
        if not all(p.isdigit() for p in parts):
            raise ValueError("Identity document must contain only digits and dashes")
        return v


class StudentProfileForUploadUrls(StudentProfileBase):
    """Student profile for upload-urls request (no document URLs)."""
    profile_picture_content_type: str = Field(
        ...,
        description="MIME type for profile picture PUT (must match Content-Type on upload; used in presigned URL)",
    )
    identity_document_content_type: str = Field(
        ...,
        description="MIME type for identity document PUT",
    )


class StudentProfileSubmit(StudentProfileBase):
    """Student profile data for application submission (includes document URLs)."""
    profile_picture_url: str = Field(..., description="URL to profile picture")
    identity_doc_url: str = Field(..., description="URL to identity document scan")


class GuardianSubmit(BaseModel):
    """Guardian information for application submission"""
    
    guardian_relationship: GuardianRelationship = Field(..., description="Relationship with student")
    first_name: str = Field(..., min_length=1, max_length=100, description="Guardian's first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Guardian's last name")
    
    cnic: Optional[str] = Field(None, min_length=15, max_length=15, description="Guardian's CNIC (optional)")
    phone_number: str = Field(..., min_length=10, max_length=20, description="Guardian's phone number")
    email: Optional[EmailStr] = Field(None, description="Guardian's email address")
    occupation: Optional[str] = Field(None, max_length=100, description="Guardian's occupation")
    
    is_primary: bool = Field(True, description="Is this the primary guardian/contact? (default: true)")


class AcademicRecordBase(BaseModel):
    """Shared academic record fields (no result_card_url)."""
    level: AcademicLevel = Field(AcademicLevel.SECONDARY, description="Academic level (default: secondary/Matric)")
    education_group: Optional[EducationGroup] = Field(None, description="Education group (required for secondary/higher secondary)")
    institute_name: str = Field(..., min_length=1, max_length=255, description="Name of educational institute")
    board_name: str = Field(..., min_length=1, max_length=100, description="Name of board (e.g., BISE Lahore, Federal Board)")
    roll_number: str = Field(..., min_length=1, max_length=50, description="Roll number")
    year_of_passing: int = Field(..., ge=1980, le=2030, description="Year of passing")
    total_marks: int = Field(..., gt=0, description="Total marks")
    obtained_marks: int = Field(..., gt=0, description="Obtained marks")
    grade: Optional[str] = Field(None, max_length=10, description="Grade (e.g., A+, A, B)")

    @field_validator("obtained_marks")
    @classmethod
    def validate_obtained_marks(cls, v: int, info) -> int:
        total_marks = info.data.get("total_marks")
        if total_marks and v > total_marks:
            raise ValueError(f"Obtained marks ({v}) cannot exceed total marks ({total_marks})")
        return v


class AcademicRecordForUploadUrls(AcademicRecordBase):
    """Academic record for upload-urls request (no result_card_url)."""
    result_card_content_type: str = Field(
        ...,
        description="MIME type for result card PUT",
    )


class AcademicRecordSubmit(AcademicRecordBase):
    """Academic record information for application submission (includes result card URL)."""
    result_card_url: str = Field(..., description="URL to result card/certificate scan")


class AppliedProgramSubmit(BaseModel):
    """Program application target information"""
    
    institute_id: UUID = Field(..., description="Institute ID")
    program_id: UUID = Field(..., description="Program ID")
    preferred_campus_id: UUID = Field(..., description="Preferred campus ID")
    quota_id: UUID = Field(..., description="Quota ID to apply under")


# ---------- Upload URLs (request: same as submit but without document URL fields) ----------

class ApplicationUploadUrlsRequest(BaseModel):
    """Request for presigned upload URLs (same as submit payload minus document URLs)."""
    student_profile: StudentProfileForUploadUrls = Field(...)
    guardian: GuardianSubmit = Field(...)
    academic_record: AcademicRecordForUploadUrls = Field(...)
    applied_programs: List[AppliedProgramSubmit] = Field(..., min_length=1)


class UploadUrlItem(BaseModel):
    """Single document: presigned PUT URL, object URL, and Content-Type for the PUT request."""
    upload_url: str = Field(..., description="Presigned URL for PUT upload")
    object_url: str = Field(..., description="Permanent URL of the object after upload")
    content_type: str = Field(
        ...,
        description="Send this exact value as the Content-Type header on PUT (must match presigned signature)",
    )


class ApplicationUploadUrlsResponse(BaseModel):
    """Response: upload token and presigned URLs for the three documents."""
    upload_token: str = Field(..., description="Token to send with submit request")
    profile_picture: UploadUrlItem = Field(...)
    identity_document: UploadUrlItem = Field(...)
    academic_result_card: UploadUrlItem = Field(...)


class ApplicationSubmitRequest(BaseModel):
    """Complete application submission request (includes upload_token from upload-urls step)."""
    upload_token: str = Field(..., min_length=1, description="Token from POST /application/upload-urls")
    student_profile: StudentProfileSubmit = Field(..., description="Student profile data")
    guardian: GuardianSubmit = Field(..., description="Guardian information")
    academic_record: AcademicRecordSubmit = Field(..., description="Academic record (Matric for now)")
    applied_programs: List[AppliedProgramSubmit] = Field(
        ...,
        min_length=1,
        description="List of programs to apply to (at least one required)",
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "upload_token": "token-from-post-application-upload-urls",
                "student_profile": {
                    "first_name": "Ahmed",
                    "last_name": "Khan",
                    "father_name": "Muhammad Khan",
                    "gender": "male",
                    "date_of_birth": "2008-05-15",
                    "identity_doc_type": "b_form",
                    "identity_doc_number": "12345-1234567-8",
                    "religion": "islam",
                    "nationality": "Pakistani",
                    "is_disabled": False,
                    "disability_details": None,
                    "primary_email": "ahmed.khan@email.com",
                    "primary_phone": "+923001234567",
                    "alternate_phone": None,
                    "street_address": "House 123, Street 5, F-10",
                    "city": "Islamabad",
                    "district": "Islamabad",
                    "province": "islamabad_capital_territory",
                    "postal_code": "44000",
                    "domicile_province": "punjab",
                    "domicile_district": "Rawalpindi",
                    "profile_picture_url": "https://s3.amazonaws.com/bucket/profile.jpg",
                    "identity_doc_url": "https://s3.amazonaws.com/bucket/cnic.jpg"
                },
                "guardian": {
                    "guardian_relationship": "father",
                    "first_name": "Muhammad",
                    "last_name": "Khan",
                    "cnic": "12345-1234567-9",
                    "phone_number": "+923009876543",
                    "email": "father@email.com",
                    "occupation": "Business"
                },
                "academic_record": {
                    "education_group": "ssc_science_biology",
                    "institute_name": "Islamabad Model School",
                    "board_name": "Federal Board",
                    "roll_number": "123456",
                    "year_of_passing": 2024,
                    "total_marks": 1100,
                    "obtained_marks": 950,
                    "grade": "A+",
                    "result_card_url": "https://s3.amazonaws.com/bucket/result.pdf"
                },
                "applied_programs": [
                    {
                        "institute_id": "123e4567-e89b-12d3-a456-426614174000",
                        "program_id": "123e4567-e89b-12d3-a456-426614174001",
                        "preferred_campus_id": "123e4567-e89b-12d3-a456-426614174002",
                        "quota_id": "123e4567-e89b-12d3-a456-426614174003"
                    }
                ]
            }
        }


class ApplicationSubmitResponse(BaseModel):
    """Response after successful application submission"""
    
    message: str = Field(..., description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Application(s) submitted successfully. Check your email for application details and login credentials."
            }
        }


# ==================== STUDENT APPLICATION LIST & DETAIL (MY APPLICATIONS) ====================


class StudentApplicationStatus(str, Enum):
    """Student-facing application status. Only mapping: internal on_hold -> under_review; all others pass through."""
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    DOCUMENTS_PENDING = "documents_pending"
    VERIFIED = "verified"
    OFFERED = "offered"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    WITHDRAWN = "withdrawn"


class StudentApplicationListItem(BaseModel):
    """Overview of one application for the student's list. No administrative details."""
    id: UUID
    application_number: str
    status: StudentApplicationStatus
    submitted_at: datetime
    institute_name: Optional[str] = None
    program_name: Optional[str] = None
    campus_name: Optional[str] = None
    quota_name: Optional[str] = None
    uploaded_documents: List[DocumentRequestItem] = Field(default_factory=list, description="Documents uploaded with application")
    requested_uploads: List[DocumentRequestItem] = Field(default_factory=list, description="Documents requested by staff with no file yet (pending upload)")
    comments: List[ApplicationCommentItem] = Field(default_factory=list, description="Merged staff (non-internal) and student comments, sorted by created_at")

    class Config:
        from_attributes = True


class StudentApplicationListResponse(BaseModel):
    """List of current student's applications (overview only) with per-status counts."""
    items: List[StudentApplicationListItem] = Field(..., description="Student's applications")
    total: int = Field(..., ge=0, description="Total count")
    submitted: int = Field(0, ge=0, description="Count of applications with status submitted")
    under_review: int = Field(0, ge=0, description="Count of applications with status under_review (includes internal on_hold)")
    documents_pending: int = Field(0, ge=0, description="Count of applications with status documents_pending")
    verified: int = Field(0, ge=0, description="Count of applications with status verified")
    offered: int = Field(0, ge=0, description="Count of applications with status offered")
    rejected: int = Field(0, ge=0, description="Count of applications with status rejected")
    accepted: int = Field(0, ge=0, description="Count of applications with status accepted")
    withdrawn: int = Field(0, ge=0, description="Count of applications with status withdrawn")


# ==================== TRACK APPLICATION (STATUS-BASED FROM LOG) ====================


class ApplicationTrackStep(BaseModel):
    """One status step in the application timeline (from log history)."""
    status: StudentApplicationStatus
    created_at: datetime


class ApplicationTrackResponse(BaseModel):
    """Status-based tracking for an application (from status_change log entries)."""
    application_number: str
    current_status: StudentApplicationStatus
    institute_name: str = Field(..., description="Name of the institute")
    programme_name: str = Field(..., description="Name of the programme")
    steps: List[ApplicationTrackStep] = Field(..., description="Chronological status steps from log")


class StudentGuardianDetail(BaseModel):
    """Guardian info from application snapshot (student-facing)."""
    id: UUID
    guardian_relationship: str
    first_name: str
    last_name: str
    phone_number: str
    email: Optional[str] = None
    occupation: Optional[str] = None

    class Config:
        from_attributes = True


class StudentAcademicRecordDetail(BaseModel):
    """Academic record from application snapshot (student-facing). No verification internals."""
    id: UUID
    level: str
    education_group: Optional[str] = None
    institute_name: str
    board_name: str
    roll_number: str
    year_of_passing: int
    total_marks: int
    obtained_marks: int
    grade: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== DOCUMENT REQUESTS (UPLOADED + REQUESTED – SAME ITEM SHAPE) ====================


class DocumentRequestItem(BaseModel):
    """A document requested by staff that is pending (student can or has uploaded)."""
    id: UUID
    document_type: str
    document_name: str
    description: Optional[str] = None
    requested_at: Optional[datetime] = None
    verification_status: VerificationStatus
    uploaded_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentRequestDetailItem(DocumentRequestItem):
    """Detailed document request item including file URL."""
    file_url: str


class DocumentRequestListResponse(BaseModel):
    """List of pending document requests for an application."""
    items: List[DocumentRequestItem] = Field(..., description="Pending document requests")


class DocumentRequestUploadUrlsRequest(BaseModel):
    """Request presigned upload URL for a requested document."""
    content_type: str = Field(
        ...,
        min_length=1,
        description="MIME type for requested document PUT",
    )


class DocumentRequestUploadUrlsResponse(BaseModel):
    """Response for requested-document upload URL."""
    upload_token: str = Field(..., description="Token to bind upload with PATCH update")
    document: UploadUrlItem = Field(...)


class DocumentRequestUploadRequest(BaseModel):
    """Body to resolve a document request by uploading via upload token."""
    upload_token: str = Field(..., min_length=1, description="Token from upload-urls endpoint")
    file_url: str = Field(..., min_length=1, max_length=500, description="Pending object URL returned from upload-urls endpoint")


# ==================== COMMENTS (MERGED STAFF + STUDENT, SAME PATTERN AS ADMIN) ====================


class ApplicationCommentItem(BaseModel):
    """Unified comment item (staff or student). Merged and sorted by created_at."""
    id: UUID
    comment_text: str
    created_at: datetime
    author_type: Literal["staff", "student"]
    author_display_name: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== STUDENT COMMENTS ====================


class StudentCommentCreate(BaseModel):
    """Request body for student to add a comment on their application."""
    comment_text: str = Field(..., min_length=1, max_length=5000, description="Comment content")


class StudentCommentItem(BaseModel):
    """Student's own comment on an application (response)."""
    id: UUID
    comment_text: str
    created_at: datetime

    class Config:
        from_attributes = True


class StudentApplicationDetailResponse(BaseModel):
    """Full application detail for the student. No assigned_to, decision_notes, workflow_instance_id, etc."""
    # Application metadata (student-visible only)
    id: UUID
    application_number: str
    status: StudentApplicationStatus
    submitted_at: datetime
    offer_expires_at: Optional[datetime] = None
    # Target
    institute_id: UUID
    institute_name: Optional[str] = None
    program_name: Optional[str] = None
    campus_name: Optional[str] = None
    quota_name: Optional[str] = None
    # Applicant snapshot (read-only as submitted)
    profile_captured_at: datetime
    first_name: str
    last_name: str
    father_name: str
    gender: str
    date_of_birth: date
    identity_doc_type: str
    identity_doc_number: str
    religion: Optional[str] = None
    nationality: str
    is_disabled: bool
    disability_details: Optional[str] = None
    primary_email: str
    primary_phone: str
    alternate_phone: Optional[str] = None
    street_address: str
    city: str
    district: str
    province: str
    postal_code: Optional[str] = None
    domicile_province: str
    domicile_district: str
    # Related (student-visible)
    guardians: List[StudentGuardianDetail] = Field(default_factory=list)
    academic_records: List[StudentAcademicRecordDetail] = Field(default_factory=list)
    uploaded_documents: List[DocumentRequestItem] = Field(default_factory=list, description="Documents uploaded with application")
    requested_uploads: List[DocumentRequestItem] = Field(default_factory=list, description="Documents requested by staff with no file yet (pending upload)")
    comments: List[ApplicationCommentItem] = Field(default_factory=list, description="Merged staff (non-internal) and student comments, sorted by created_at")

    class Config:
        from_attributes = True

