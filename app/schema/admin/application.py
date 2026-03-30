"""Admin application list and detail schemas."""
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.database.models.application import ApplicationStatus, DocumentType, VerificationStatus
from app.database.models.workflow import WorkflowStepStatus


class ApplicationListStudentSummary(BaseModel):
    """Basic student info for list view."""
    first_name: str
    last_name: str
    primary_email: str
    identity_number: str

    class Config:
        from_attributes = True


class ApplicationListItem(BaseModel):
    """Application list item: basic metadata for admin list view."""
    id: UUID
    application_number: str
    status: str
    submitted_at: datetime
    last_updated_at: Optional[datetime] = None
    offer_expires_at: Optional[datetime] = None
    # Student (from student_profile)
    student: ApplicationListStudentSummary
    # Target
    preferred_campus_id: UUID
    preferred_campus_name: Optional[str] = None
    preferred_program_cycle_id: UUID
    program_name: Optional[str] = None
    quota_id: Optional[UUID] = None
    quota_name: Optional[str] = None
    # Assignment
    assigned_to_id: Optional[UUID] = None
    assigned_to_name: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedApplicationListResponse(BaseModel):
    """List response with total count."""
    items: List[ApplicationListItem] = Field(..., description="Page of application items")
    total: int = Field(..., ge=0, description="Total number of items matching the filters")


# ==================== APPLICATION DETAIL (no docs) ====================


class GuardianDetail(BaseModel):
    """Guardian info for application detail (no docs)."""
    id: UUID
    guardian_relationship: str
    first_name: str
    last_name: str
    cnic: Optional[str] = None
    phone_number: str
    email: Optional[str] = None
    occupation: Optional[str] = None
    is_primary: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AcademicRecordDetail(BaseModel):
    """Academic record for application detail (no doc URLs)."""
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
    # Academic record verification skipped for now (ignore until we implement verification flow).
    # is_verified: bool
    # verification_status: str
    # verified_by: Optional[UUID] = None
    # verified_at: Optional[datetime] = None
    # verification_notes: Optional[str] = None
    # rejection_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationDetailResponse(BaseModel):
    """Full application detail: application metadata + applicant info + guardians + academic records (no docs)."""
    # Application metadata
    id: UUID
    application_number: str
    institute_id: UUID
    status: ApplicationStatus = Field(..., description="Application status (e.g. submitted, verified, offered, rejected, on_hold)")
    submitted_at: datetime
    last_updated_at: Optional[datetime] = None
    decision_notes: Optional[str] = None
    offer_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    preferred_campus_id: UUID
    preferred_campus_name: Optional[str] = None
    preferred_program_cycle_id: UUID
    program_name: Optional[str] = None
    quota_id: Optional[UUID] = None
    quota_name: Optional[str] = None
    assigned_to_id: Optional[UUID] = None
    assigned_to_name: Optional[str] = None
    workflow_instance_id: Optional[UUID] = None
    # Applicant info (captured at submission)
    profile_captured_at: datetime
    first_name: str
    last_name: str
    father_name: str
    gender: str
    date_of_birth: date
    identity_doc_number: str
    identity_doc_type: str
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
    # Related lists (use default_factory so Swagger/OpenAPI resolve schema)
    guardians: List[GuardianDetail] = Field(default_factory=list)
    academic_records: List[AcademicRecordDetail] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ==================== APPLICATION LOG HISTORY ====================


class ApplicationLogChangedByUser(BaseModel):
    """Actor who performed the logged action (when not system)."""
    id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class ApplicationLogHistoryItem(BaseModel):
    """One audit row from application_log_history."""
    id: UUID
    application_id: UUID
    action_type: str
    details: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    performed_by: Optional[ApplicationLogChangedByUser] = None
    created_at: datetime


# ==================== APPLICATION DOCUMENTS ====================


class ApplicationDocumentListItem(BaseModel):
    """Single application document for list response (no file URL)."""
    id: UUID
    document_type: DocumentType
    document_name: str
    description: Optional[str] = None
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    is_required: bool
    requested_by: Optional[UUID] = None
    requested_at: Optional[datetime] = None
    uploaded_at: Optional[datetime] = None
    verification_status: VerificationStatus
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationDocumentItem(ApplicationDocumentListItem):
    """Single application document detail response (includes file URL)."""
    file_url: Optional[str] = None


class DocumentRequestCreate(BaseModel):
    """Request body for creating a document request (admin requests a document from student)."""
    document_type: DocumentType = Field(..., description="Type of document (use 'other' for requested docs)")
    document_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_required: bool = Field(True, description="Whether the document is required")


class DocumentVerificationUpdate(BaseModel):
    """Request body for updating document verification status."""
    verification_status: VerificationStatus = Field(..., description="New verification status")
    rejection_reason: Optional[str] = Field(None, description="Required when rejecting")


# ==================== APPLICATION COMMENTS (MERGED STAFF + STUDENT) ====================


class StaffCommentCreate(BaseModel):
    """Request body for staff to add a comment on an application."""
    comment_text: str = Field(..., min_length=1, description="Comment content")
    is_internal: bool = Field(False, description="If true, comment is internal (not visible to student)")


class ApplicationCommentItem(BaseModel):
    """Unified comment item (staff or student). Sorted by created_at in the list endpoint."""
    id: UUID
    comment_text: str
    created_at: datetime
    author_type: Literal["staff", "student"]
    is_internal: Optional[bool] = None  # Staff only: internal vs visible to student
    author_display_name: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== APPLICATION PROGRESS (WORKFLOW STEPS) ====================


class CompleteTaskRequest(BaseModel):
    """Request body to complete a workflow user task."""
    task_id: str = Field(..., description="BPMN task ID (from progress current_tasks)")
    data: Optional[Dict[str, Any]] = Field(None, description="Task payload to inject into workflow data")


class WorkflowStepItem(BaseModel):
    """One step in application workflow progress."""

    id: UUID
    workflow_instance_id: UUID
    subflow_key: str
    subflow_version: int
    process_id: str
    name: Optional[str] = None
    display_order: int
    status: WorkflowStepStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    current_tasks: Optional[Any] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "workflow_instance_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "subflow_key": "operation.verify_documents",
                "subflow_version": 1,
                "process_id": "operation.verify_documents_v1",
                "name": "Verify Documents",
                "display_order": 0,
                "status": "pending",
                "started_at": "2026-03-06T10:00:00Z",
                "completed_at": "2026-03-06T10:00:05Z",
                "error_message": None,
                "current_tasks": ["verify_documents_v1.verify_documents"],
            }
        }
