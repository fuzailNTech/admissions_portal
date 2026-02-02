from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List, Any
from datetime import datetime, date
from uuid import UUID


# Import enums from models
from app.database.models.admission import (
    AcademicSession,
    AdmissionCycleStatus,
    QuotaType,
    QuotaStatus,
    FieldType,
)


# AdmissionCycle Schemas
class AdmissionCycleCreate(BaseModel):
    """Create admission cycle (institute-wide)"""
    name: str = Field(..., min_length=1, description="e.g., Admissions 2026-27")
    academic_year: str = Field(..., description="e.g., 2026-27")
    session: AcademicSession = AcademicSession.ANNUAL
    application_start_date: datetime
    application_end_date: datetime
    description: Optional[str] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_published: bool = False


class AdmissionCycleUpdate(BaseModel):
    """Update admission cycle"""
    name: Optional[str] = Field(None, min_length=1)
    academic_year: Optional[str] = None
    session: Optional[AcademicSession] = None
    status: Optional[AdmissionCycleStatus] = None
    application_start_date: Optional[datetime] = None
    application_end_date: Optional[datetime] = None
    description: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None
    is_published: Optional[bool] = None


class AdmissionCycleResponse(BaseModel):
    """Admission cycle response"""
    id: UUID
    institute_id: UUID
    name: str
    academic_year: str
    session: AcademicSession
    status: AdmissionCycleStatus
    application_start_date: datetime
    application_end_date: datetime
    description: Optional[str]
    custom_metadata: Dict[str, Any]
    is_published: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[UUID]

    class Config:
        from_attributes = True


# CampusAdmissionCycle Schemas (Junction Table)
class CampusAdmissionCycleCreate(BaseModel):
    """Assign admission cycle to a campus"""
    admission_cycle_id: UUID
    is_open: bool = True
    closure_reason: Optional[str] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)


class CampusAdmissionCycleUpdate(BaseModel):
    """Update campus admission cycle"""
    is_open: Optional[bool] = None
    closure_reason: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None


class CampusAdmissionCycleResponse(BaseModel):
    """Campus admission cycle response"""
    id: UUID
    campus_id: UUID
    admission_cycle_id: UUID
    is_open: bool
    closure_reason: Optional[str]
    custom_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[UUID]

    class Config:
        from_attributes = True


class CampusAdmissionCycleDetailResponse(BaseModel):
    """Detailed campus admission cycle response with nested admission cycle"""
    id: UUID
    campus_id: UUID
    is_open: bool
    closure_reason: Optional[str]
    custom_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[UUID]
    admission_cycle: AdmissionCycleResponse  # Nested admission cycle details

    class Config:
        from_attributes = True


# ProgramAdmissionCycle Schemas
class QuotaCreateNested(BaseModel):
    """Nested quota creation schema for use in ProgramAdmissionCycleCreate"""
    quota_type: QuotaType
    quota_name: str = Field(..., min_length=1, max_length=255, description="e.g., Open Merit, Hafiz-e-Quran")
    allocated_seats: int = Field(..., gt=0, description="Number of seats for this quota")
    eligibility_requirements: Dict[str, Any] = Field(default_factory=dict)
    required_documents: List[Any] = Field(default_factory=list)
    minimum_marks: Optional[int] = Field(None, ge=0, le=100)
    priority_order: int = Field(default=0, description="Order for merit list generation")
    description: Optional[str] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)


class ProgramAdmissionCycleCreate(BaseModel):
    """Add program to a campus admission cycle with quotas"""
    program_id: UUID
    total_seats: int = Field(..., gt=0, description="Total seats for this program")
    description: Optional[str] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    quotas: List[QuotaCreateNested] = Field(..., min_length=1, description="At least one quota is required")
    
    @field_validator('quotas')
    @classmethod
    def validate_quotas(cls, quotas, info):
        """Validate that at least one quota is provided and total allocated seats don't exceed total_seats"""
        if not quotas:
            raise ValueError("At least one quota is required")
        
        # Get total_seats from the data being validated
        total_seats = info.data.get('total_seats')
        if total_seats:
            total_allocated = sum(q.allocated_seats for q in quotas)
            if total_allocated > total_seats:
                raise ValueError(
                    f"Sum of allocated seats ({total_allocated}) cannot exceed total_seats ({total_seats})"
                )
        
        return quotas


class ProgramAdmissionCycleUpdate(BaseModel):
    """Update program admission cycle"""
    total_seats: Optional[int] = Field(None, gt=0)
    seats_filled: Optional[int] = Field(None, ge=0)
    description: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ProgramAdmissionCycleResponse(BaseModel):
    """Program admission cycle response"""
    id: UUID
    campus_admission_cycle_id: UUID
    program_id: UUID
    total_seats: int
    seats_filled: int
    description: Optional[str]
    custom_metadata: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Import ProgramResponse from institute schemas
from app.schema.admin.institute import ProgramResponse


class ProgramAdmissionCycleDetailResponse(BaseModel):
    """Detailed program admission cycle response with nested program details"""
    id: UUID
    campus_admission_cycle_id: UUID
    total_seats: int
    seats_filled: int
    description: Optional[str]
    custom_metadata: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    program: ProgramResponse  # Nested program details

    class Config:
        from_attributes = True


# Forward reference for ProgramQuotaResponse (defined below)
class ProgramAdmissionCycleWithQuotasResponse(BaseModel):
    """Detailed program admission cycle with program details and all quotas"""
    id: UUID
    campus_admission_cycle_id: UUID
    total_seats: int
    seats_filled: int
    description: Optional[str]
    custom_metadata: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    program: ProgramResponse  # Nested program details
    quotas: List['ProgramQuotaResponse']  # All quotas for this program cycle

    class Config:
        from_attributes = True


# ProgramQuota Schemas
class ProgramQuotaCreate(BaseModel):
    """Create a quota for a program cycle"""
    quota_type: QuotaType
    quota_name: str = Field(..., min_length=1, max_length=255, description="e.g., Open Merit, Hafiz-e-Quran")
    allocated_seats: int = Field(..., gt=0, description="Number of seats for this quota")
    eligibility_requirements: Dict[str, Any] = Field(default_factory=dict)
    required_documents: List[Any] = Field(default_factory=list)
    minimum_marks: Optional[int] = Field(None, ge=0, le=100)
    priority_order: int = Field(default=0, description="Order for merit list generation")
    description: Optional[str] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)


class ProgramQuotaUpdate(BaseModel):
    """Update program quota"""
    quota_name: Optional[str] = Field(None, min_length=1, max_length=255)
    allocated_seats: Optional[int] = Field(None, gt=0)
    seats_filled: Optional[int] = Field(None, ge=0)
    eligibility_requirements: Optional[Dict[str, Any]] = None
    required_documents: Optional[List[Any]] = None
    minimum_marks: Optional[int] = Field(None, ge=0, le=100)
    priority_order: Optional[int] = None
    status: Optional[QuotaStatus] = None
    description: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None


class ProgramQuotaResponse(BaseModel):
    """Program quota response"""
    id: UUID
    program_cycle_id: UUID
    quota_type: QuotaType
    quota_name: str
    allocated_seats: int
    seats_filled: int
    eligibility_requirements: Dict[str, Any]
    required_documents: List[Any]
    minimum_marks: Optional[int]
    priority_order: int
    status: QuotaStatus
    description: Optional[str]
    custom_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# CustomFormField Schemas
class CustomFormFieldCreate(BaseModel):
    """Create a custom form field for the institute"""
    field_name: str = Field(..., min_length=1, max_length=100, description="Internal identifier (e.g., why_premed)")
    label: str = Field(..., min_length=1, max_length=255, description="Display label for the field")
    field_type: FieldType
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    default_value: Optional[str] = None
    min_length: Optional[int] = Field(None, ge=0)
    max_length: Optional[int] = Field(None, ge=0)
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    pattern: Optional[str] = Field(None, description="Regex pattern for validation")
    options: List[Any] = Field(default_factory=list, description="Options for select/radio/checkbox")
    description: Optional[str] = Field(None, description="Field description for admin")
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class CustomFormFieldUpdate(BaseModel):
    """Update custom form field"""
    field_name: Optional[str] = Field(None, min_length=1, max_length=100)
    label: Optional[str] = Field(None, min_length=1, max_length=255)
    field_type: Optional[FieldType] = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    default_value: Optional[str] = None
    min_length: Optional[int] = Field(None, ge=0)
    max_length: Optional[int] = Field(None, ge=0)
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    pattern: Optional[str] = None
    options: Optional[List[Any]] = None
    description: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class CustomFormFieldResponse(BaseModel):
    """Custom form field response"""
    id: UUID
    institute_id: UUID
    field_name: str
    label: str
    field_type: FieldType
    placeholder: Optional[str]
    help_text: Optional[str]
    default_value: Optional[str]
    min_length: Optional[int]
    max_length: Optional[int]
    min_value: Optional[int]
    max_value: Optional[int]
    pattern: Optional[str]
    options: List[Any]
    description: Optional[str]
    custom_metadata: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[UUID]

    class Config:
        from_attributes = True


# ProgramFormField Schemas
class ProgramFormFieldCreate(BaseModel):
    """Assign a custom form field to a program"""
    form_field_id: UUID
    is_required: bool = False
    display_order: int = Field(default=0, description="Order for displaying fields")


class ProgramFormFieldUpdate(BaseModel):
    """Update program form field assignment"""
    is_required: Optional[bool] = None
    display_order: Optional[int] = None


class ProgramFormFieldResponse(BaseModel):
    """Program form field response"""
    id: UUID
    program_id: UUID
    form_field_id: UUID
    is_required: bool
    display_order: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ProgramFormFieldDetailResponse(BaseModel):
    """Detailed program form field with nested form field details"""
    id: UUID
    program_id: UUID
    is_required: bool
    display_order: int
    created_at: datetime
    updated_at: Optional[datetime]
    form_field: CustomFormFieldResponse  # Nested form field details

    class Config:
        from_attributes = True
