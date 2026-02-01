from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID


# ==================== ACTIVE CYCLE INFO ====================

class ActiveCycleInfo(BaseModel):
    """Active admission cycle basic information"""
    id: UUID
    name: str
    academic_year: str
    status: str
    application_start_date: datetime
    application_end_date: datetime
    is_published: bool
    
    class Config:
        from_attributes = True


# ==================== LIST VIEW SCHEMAS ====================

class CampusBasicInfo(BaseModel):
    """Basic campus information for listing"""
    id: UUID
    name: str
    campus_type: str
    city: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True


class InstituteBasicInfo(BaseModel):
    """Basic institute information for listing"""
    id: UUID
    name: str
    institute_code: str
    institute_type: str
    institute_level: str
    established_year: Optional[int]
    
    active_cycle: Optional[ActiveCycleInfo]
    campuses: List[CampusBasicInfo]
    
    class Config:
        from_attributes = True


class InstituteListResponse(BaseModel):
    """Response for institute listing"""
    total: int
    institutes: List[InstituteBasicInfo]


# ==================== DETAIL VIEW SCHEMAS ====================

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


class CampusOfferingDetail(BaseModel):
    """Campus offering details for a specific program"""
    # Campus Info
    campus_id: UUID
    campus_name: str
    campus_type: str
    campus_code: Optional[str]
    city: Optional[str]
    address_line: Optional[str]
    campus_phone: Optional[str]
    campus_email: Optional[str]
    
    # Admission Status
    admission_open: bool
    closure_reason: Optional[str]
    
    # Seat Information
    total_seats: int
    seats_filled: int
    seats_available: int
    
    # Quotas
    quotas: List[QuotaDetail]
    
    class Config:
        from_attributes = True


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
    display_order: int
    
    class Config:
        from_attributes = True


class ProgramWithOfferings(BaseModel):
    """Program information with campus offerings"""
    # Program Info
    id: UUID
    name: str
    code: str
    level: str
    category: Optional[str]
    duration_years: Optional[int]
    description: Optional[str]
    
    # Form Fields (program-level)
    custom_form_fields: List[CustomFormFieldDetail]
    
    # Campus Offerings (where this program is available)
    campus_offerings: List[CampusOfferingDetail]
    
    class Config:
        from_attributes = True


class ActiveCycleDetail(BaseModel):
    """Active admission cycle detailed information"""
    id: UUID
    name: str
    academic_year: str
    session: str
    status: str
    application_start_date: datetime
    application_end_date: datetime
    description: Optional[str]
    
    class Config:
        from_attributes = True


class InstituteDetailedInfo(BaseModel):
    """Detailed institute information with programs and offerings"""
    # Institute Info
    id: UUID
    name: str
    institute_code: str
    institute_type: str
    institute_level: str
    established_year: Optional[int]
    regulatory_body: Optional[str]
    registration_number: Optional[str]
    primary_email: Optional[str]
    primary_phone: Optional[str]
    website_url: Optional[str]
    
    # Active Cycle
    active_cycle: Optional[ActiveCycleDetail]
    
    # Programs with campus offerings
    programs: List[ProgramWithOfferings]
    
    class Config:
        from_attributes = True
