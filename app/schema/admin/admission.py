from pydantic import BaseModel, Field
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
    campus_id: UUID
    name: str = Field(..., min_length=1, description="e.g., Admissions 2026-27")
    academic_year: str = Field(..., description="e.g., 2026-27")
    session: AcademicSession = AcademicSession.ANNUAL
    application_start_date: datetime
    application_end_date: datetime
    description: Optional[str] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_published: bool = False


class AdmissionCycleUpdate(BaseModel):
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
    id: UUID
    campus_id: UUID
    name: str
    academic_year: str
    session: AcademicSession
    status: AdmissionCycleStatus
    application_start_date: datetime
    application_end_date: datetime
    description: Optional[str]
    is_published: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ProgramAdmissionCycle Schemas
class ProgramAdmissionCycleCreate(BaseModel):
    admission_cycle_id: UUID
    program_id: UUID
    total_seats: int = Field(..., gt=0)
    minimum_marks_required: Optional[int] = Field(None, ge=0, le=100)
    eligibility_criteria: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ProgramAdmissionCycleUpdate(BaseModel):
    total_seats: Optional[int] = Field(None, gt=0)
    seats_filled: Optional[int] = Field(None, ge=0)
    minimum_marks_required: Optional[int] = Field(None, ge=0, le=100)
    eligibility_criteria: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ProgramAdmissionCycleResponse(BaseModel):
    id: UUID
    admission_cycle_id: UUID
    program_id: UUID
    total_seats: int
    seats_filled: int
    minimum_marks_required: Optional[int]
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ProgramQuota Schemas
class ProgramQuotaCreate(BaseModel):
    program_cycle_id: UUID
    quota_type: QuotaType
    quota_name: str = Field(..., min_length=1, max_length=255)
    allocated_seats: int = Field(..., gt=0)
    eligibility_requirements: Dict[str, Any] = Field(default_factory=dict)
    required_documents: List[Any] = Field(default_factory=list)
    minimum_marks: Optional[int] = Field(None, ge=0, le=100)
    priority_order: int = Field(default=0)
    description: Optional[str] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)


class ProgramQuotaUpdate(BaseModel):
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
    id: UUID
    program_cycle_id: UUID
    quota_type: QuotaType
    quota_name: str
    allocated_seats: int
    seats_filled: int
    minimum_marks: Optional[int]
    priority_order: int
    status: QuotaStatus
    description: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# CustomFormField Schemas
class CustomFormFieldCreate(BaseModel):
    institute_id: UUID
    field_name: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=255)
    field_type: FieldType
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    default_value: Optional[str] = None
    min_length: Optional[int] = Field(None, ge=0)
    max_length: Optional[int] = Field(None, ge=0)
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    pattern: Optional[str] = None
    options: List[Any] = Field(default_factory=list)
    description: Optional[str] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class CustomFormFieldUpdate(BaseModel):
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
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ProgramFormField Schemas
class ProgramFormFieldCreate(BaseModel):
    program_cycle_id: UUID
    form_field_id: UUID
    is_required: bool = False


class ProgramFormFieldUpdate(BaseModel):
    is_required: Optional[bool] = None


class ProgramFormFieldResponse(BaseModel):
    id: UUID
    program_cycle_id: UUID
    form_field_id: UUID
    is_required: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
