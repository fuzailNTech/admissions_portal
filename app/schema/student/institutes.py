from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from uuid import UUID


# ==================== BASIC RESPONSES ====================

class CampusBasicInfo(BaseModel):
    """Basic campus information for listing"""
    id: UUID
    name: str
    campus_code: Optional[str]
    campus_type: str
    city: Optional[str]
    province_state: Optional[str]
    country: str
    is_active: bool
    
    class Config:
        from_attributes = True

class ProgramBasicInfo(BaseModel):
    """Basic program information for listing"""
    id: UUID
    name: str
    code: str
    level: str
    category: Optional[str]
    duration_years: Optional[int]
    
    class Config:
        from_attributes = True


class InstituteBasicInfo(BaseModel):
    """Basic institute information for listing"""
    id: UUID
    name: str
    institute_code: str
    institute_type: str
    institute_level: str
    status: str
    campuses: List[CampusBasicInfo]
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Government College Lahore",
                "institute_code": "GCL",
                "institute_type": "government",
                "institute_level": "college",
                "status": "active",
                "campuses": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174002",
                        "name": "Main Campus",
                        "campus_code": "MAIN",
                        "campus_type": "co_ed",
                        "city": "Lahore",
                        "province_state": "Punjab",
                        "country": "Pakistan",
                        "is_active": True
                    }
                ]
            }
        }


# ==================== DETAILED RESPONSES ====================

class CustomFormFieldDetail(BaseModel):
    """Custom form field details for students"""
    id: UUID
    field_name: str
    label: str
    field_type: str
    placeholder: Optional[str]
    help_text: Optional[str]
    default_value: Optional[str]
    min_length: Optional[int]
    max_length: Optional[int]
    min_value: Optional[int]
    max_value: Optional[int]
    pattern: Optional[str]
    options: List[Any]
    is_required: bool  # From ProgramFormField junction
    
    class Config:
        from_attributes = True


class QuotaDetail(BaseModel):
    """Quota details for students"""
    id: UUID
    quota_type: str
    quota_name: str
    allocated_seats: int
    seats_filled: int
    seats_available: int
    minimum_marks: Optional[int]
    priority_order: int
    status: str
    description: Optional[str]
    eligibility_requirements: Dict[str, Any]
    required_documents: List[Any]
    
    class Config:
        from_attributes = True


class ProgramCycleDetail(BaseModel):
    """Detailed program information within a cycle"""
    id: UUID
    program_id: UUID
    program_name: str
    program_code: str
    program_level: str
    program_category: Optional[str]
    
    # Seats
    total_seats: int
    seats_filled: int
    seats_available: int
    
    # Requirements
    minimum_marks_required: Optional[int]
    eligibility_criteria: Dict[str, Any]
    description: Optional[str]
    
    # Related data
    quotas: List[QuotaDetail]
    custom_form_fields: List[CustomFormFieldDetail]
    is_active: bool
    
    class Config:
        from_attributes = True


class AdmissionCycleDetail(BaseModel):
    """Admission cycle details"""
    id: UUID
    name: str
    academic_year: str
    session: str
    status: str
    application_start_date: datetime
    application_end_date: datetime
    description: Optional[str]
    is_published: bool
    
    class Config:
        from_attributes = True


class CampusDetailedInfo(BaseModel):
    """Detailed campus information with all admission details"""
    # Campus Info
    id: UUID
    name: str
    campus_code: Optional[str]
    campus_type: str
    
    # Location
    country: str
    province_state: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    address_line: Optional[str]
    
    # Contact
    campus_email: Optional[str]
    campus_phone: Optional[str]
    
    # Admission Information
    admission_cycles: List[AdmissionCycleDetail]
    programs: List[ProgramCycleDetail]
    
    class Config:
        from_attributes = True


class InstituteDetailedInfo(BaseModel):
    """Detailed institute information with campuses"""
    # Institute Info
    id: UUID
    name: str
    institute_code: str
    institute_type: str
    institute_level: str
    status: str
    
    # Official Information
    registration_number: Optional[str]
    regulatory_body: Optional[str]
    established_year: Optional[int]
    
    # Contact Information
    primary_email: Optional[str]
    primary_phone: Optional[str]
    website_url: Optional[str]
    
    # Campuses with full details
    campuses: List[CampusDetailedInfo]
    
    class Config:
        from_attributes = True


class InstituteListResponse(BaseModel):
    """Response for institute listing"""
    total: int
    institutes: List[InstituteBasicInfo]
