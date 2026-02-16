from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime, date
from uuid import UUID


# Import enums from models
from app.database.models.institute import CampusType, InstituteType, InstituteStatus, InstituteLevel


# Institute Schemas
class InstituteResponse(BaseModel):
    """Institute information response for staff."""
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
    
    class Config:
        from_attributes = True


# Campus Schemas
class CampusCreate(BaseModel):
    institute_id: Optional[UUID] = None  # Will be set from staff's institute
    name: str = Field(..., min_length=1, max_length=255, description="Campus name")
    campus_code: Optional[str] = Field(None, max_length=50)
    campus_type: CampusType
    country: str = Field(default="Pakistan")
    province_state: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address_line: Optional[str] = None
    campus_email: Optional[str] = None
    campus_phone: Optional[str] = None
    timezone: str = Field(default="Asia/Karachi")
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class CampusUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    campus_code: Optional[str] = Field(None, max_length=50)
    campus_type: Optional[CampusType] = None
    country: Optional[str] = None
    province_state: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    address_line: Optional[str] = None
    campus_email: Optional[str] = None
    campus_phone: Optional[str] = None
    timezone: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class CampusResponse(BaseModel):
    id: UUID
    institute_id: UUID
    name: str
    campus_code: Optional[str]
    campus_type: CampusType
    country: str
    province_state: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    address_line: Optional[str]
    campus_email: Optional[str]
    campus_phone: Optional[str]
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Program Schemas
class ProgramCreate(BaseModel):
    institute_id: Optional[UUID] = None  # Will be set from staff's institute
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    level: str = Field(..., description="Intermediate, Bachelors, Masters, PhD")
    category: Optional[str] = Field(None, description="Science, Arts, Commerce")
    duration_years: Optional[int] = Field(None, ge=1, le=10)
    fee: Optional[float] = Field(None, ge=0, description="Program fee amount")
    shift: str = Field(default="morning", description="morning, afternoon, evening")
    description: Optional[str] = None
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ProgramUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    level: Optional[str] = None
    category: Optional[str] = None
    duration_years: Optional[int] = Field(None, ge=1, le=10)
    fee: Optional[float] = Field(None, ge=0)
    shift: Optional[str] = Field(None, description="morning, afternoon, evening")
    description: Optional[str] = None
    custom_metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ProgramResponse(BaseModel):
    id: UUID
    institute_id: UUID
    name: str
    code: str
    level: str
    category: Optional[str]
    duration_years: Optional[int]
    fee: Optional[float]
    shift: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# CampusProgram Schemas (Junction Table)
class CampusProgramCreate(BaseModel):
    program_id: UUID
    is_active: bool = True


class CampusProgramUpdate(BaseModel):
    is_active: Optional[bool] = None


class CampusProgramResponse(BaseModel):
    id: UUID
    campus_id: UUID
    program_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# Detailed CampusProgram Response (for GET /campus/{id}/campus-programs)
class ProgramInCampusResponse(BaseModel):
    """Program details with campus-program junction info."""
    id: UUID
    name: str
    code: str
    level: str
    category: Optional[str]
    duration_years: Optional[int]
    fee: Optional[float]
    shift: str
    description: Optional[str]
    is_active: bool  # From Program table
    campus_program_id: UUID  # From CampusProgram junction table
    campus_program_is_active: bool  # From CampusProgram junction table
    campus_program_created_at: datetime
    campus_program_updated_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]


class CampusWithProgramsResponse(BaseModel):
    """Campus info with all assigned programs."""
    id: UUID
    institute_id: UUID
    name: str
    campus_code: Optional[str]
    campus_type: CampusType
    country: str
    province_state: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    address_line: Optional[str]
    campus_email: Optional[str]
    campus_phone: Optional[str]
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    programs: List[ProgramInCampusResponse]
