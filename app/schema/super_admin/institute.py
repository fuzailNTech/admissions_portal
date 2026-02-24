from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
import re

# Import enums from models
from app.database.models.institute import InstituteType, InstituteStatus, InstituteLevel
from app.database.models.auth import StaffRoleType

# Avoid circular import: use TYPE_CHECKING or import response schema from workflow_definition
from app.schema.super_admin.workflow_definition import WorkflowDefinitionResponse


class InstituteCreate(BaseModel):
    """Schema for creating a new institute."""
    name: str = Field(..., min_length=1, max_length=255, description="Name of the institute")
    institute_code: str = Field(..., min_length=1, max_length=50, description="Unique code for CMS linking")
    institute_type: InstituteType
    institute_level: InstituteLevel
    status: InstituteStatus = InstituteStatus.ACTIVE
    
    # Optional fields
    registration_number: Optional[str] = None
    regulatory_body: Optional[str] = Field(None, description="e.g., BISE Lahore, HEC, PEC, PMDC")
    established_year: Optional[int] = Field(None, ge=1800, le=2100)
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    website_url: Optional[str] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('institute_code')
    @classmethod
    def validate_institute_code(cls, v: str) -> str:
        """Validate institute code format."""
        if not re.match(r'^[A-Z0-9_-]+$', v):
            raise ValueError('Institute code must contain only uppercase letters, numbers, underscores, and hyphens')
        return v


class InstituteUpdate(BaseModel):
    """Schema for updating an institute."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    institute_code: Optional[str] = Field(None, min_length=1, max_length=50)
    institute_type: Optional[InstituteType] = None
    institute_level: Optional[InstituteLevel] = None
    status: Optional[InstituteStatus] = None
    registration_number: Optional[str] = None
    regulatory_body: Optional[str] = None
    established_year: Optional[int] = Field(None, ge=1800, le=2100)
    primary_email: Optional[EmailStr] = None
    primary_phone: Optional[str] = None
    website_url: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None

    @field_validator('institute_code')
    @classmethod
    def validate_institute_code(cls, v: Optional[str]) -> Optional[str]:
        """Validate institute code format if provided."""
        if v is not None and not re.match(r'^[A-Z0-9_-]+$', v):
            raise ValueError('Institute code must contain only uppercase letters, numbers, underscores, and hyphens')
        return v


class InstituteResponse(BaseModel):
    """Schema for institute response."""
    id: UUID
    name: str
    institute_code: str
    institute_type: InstituteType
    institute_level: InstituteLevel
    status: InstituteStatus
    registration_number: Optional[str]
    regulatory_body: Optional[str]
    established_year: Optional[int]
    primary_email: Optional[str]
    primary_phone: Optional[str]
    website_url: Optional[str]
    custom_metadata: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[UUID]

    class Config:
        from_attributes = True


class InstituteAdminResponse(BaseModel):
    """Staff/admin of an institute (for institute detail response)."""
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    role: StaffRoleType
    is_active: bool
    assigned_at: datetime

    class Config:
        from_attributes = True


class InstituteDetailResponse(InstituteResponse):
    """Institute response including workflow_definitions (without bpmn_xml) and admins."""
    workflow_definitions: List[WorkflowDefinitionResponse] = []
    admins: List[InstituteAdminResponse] = []

    class Config:
        from_attributes = True


class AssignInstituteAdminRequest(BaseModel):
    """Request to assign an institute admin. institute_id is in the path; first_name and last_name are taken from the user record."""
    user_id: UUID = Field(..., description="User ID to assign as admin")


class AssignInstituteAdminResponse(BaseModel):
    """Response after assigning institute admin."""
    staff_profile_id: UUID
    user_id: UUID
    institute_id: UUID
    assigned_at: datetime

    class Config:
        from_attributes = True

