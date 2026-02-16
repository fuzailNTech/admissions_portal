from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, date

# Import enums from models
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
    current_tasks: Optional[list]
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ==================== STUDENT APPLICATION SUBMISSION ====================

class StudentProfileSubmit(BaseModel):
    """Student profile data for application submission"""
    
    # Personal Information
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    father_name: str = Field(..., min_length=1, max_length=100, description="Father's name")
    
    gender: GenderType = Field(..., description="Gender")
    date_of_birth: date = Field(..., description="Date of birth")
    
    # Identity Document
    identity_doc_type: IdentityDocumentType = Field(..., description="Type of identity document (CNIC or B-Form)")
    identity_doc_number: str = Field(..., min_length=15, max_length=15, description="Identity document number (format: XXXXX-XXXXXXX-X)")
    
    religion: Optional[ReligionType] = Field(None, description="Religion")
    nationality: str = Field(default="Pakistani", max_length=50, description="Nationality")
    
    # Disability Information
    is_disabled: bool = Field(default=False, description="Is the student disabled?")
    disability_details: Optional[str] = Field(None, description="Details about disability if applicable")
    
    # Contact Information
    primary_email: EmailStr = Field(..., description="Primary email address")
    primary_phone: str = Field(..., min_length=10, max_length=20, description="Primary phone number")
    alternate_phone: Optional[str] = Field(None, min_length=10, max_length=20, description="Alternate phone number")
    
    # Address
    street_address: str = Field(..., min_length=1, description="Street address")
    city: str = Field(..., min_length=1, max_length=100, description="City")
    district: str = Field(..., min_length=1, max_length=100, description="District")
    province: ProvinceType = Field(..., description="Province")
    postal_code: Optional[str] = Field(None, max_length=10, description="Postal code")
    
    # Domicile
    domicile_province: ProvinceType = Field(..., description="Domicile province")
    domicile_district: str = Field(..., min_length=1, max_length=100, description="Domicile district")
    
    # Documents (S3 URLs)
    profile_picture_url: str = Field(..., description="URL to profile picture")
    identity_doc_url: str = Field(..., description="URL to identity document scan")
    
    @field_validator('identity_doc_number')
    @classmethod
    def validate_identity_doc_format(cls, v: str) -> str:
        """Validate CNIC/B-Form format: XXXXX-XXXXXXX-X"""
        if not v or len(v) != 15:
            raise ValueError('Identity document must be 15 characters (format: XXXXX-XXXXXXX-X)')
        
        parts = v.split('-')
        if len(parts) != 3:
            raise ValueError('Identity document format must be: XXXXX-XXXXXXX-X')
        
        if len(parts[0]) != 5 or len(parts[1]) != 7 or len(parts[2]) != 1:
            raise ValueError('Identity document format must be: XXXXX-XXXXXXX-X')
        
        if not all(part.isdigit() for part in parts):
            raise ValueError('Identity document must contain only digits and dashes')
        
        return v


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


class AcademicRecordSubmit(BaseModel):
    """Academic record information for application submission"""
    
    level: AcademicLevel = Field(AcademicLevel.SECONDARY, description="Academic level (default: secondary/Matric)")
    education_group: Optional[EducationGroup] = Field(None, description="Education group (required for secondary/higher secondary)")
    
    institute_name: str = Field(..., min_length=1, max_length=255, description="Name of educational institute")
    board_name: str = Field(..., min_length=1, max_length=100, description="Name of board (e.g., BISE Lahore, Federal Board)")
    roll_number: str = Field(..., min_length=1, max_length=50, description="Roll number")
    year_of_passing: int = Field(..., ge=1980, le=2030, description="Year of passing")
    
    total_marks: int = Field(..., gt=0, description="Total marks")
    obtained_marks: int = Field(..., gt=0, description="Obtained marks")
    grade: Optional[str] = Field(None, max_length=10, description="Grade (e.g., A+, A, B)")
    
    # Document (S3 URL)
    result_card_url: str = Field(..., description="URL to result card/certificate scan")
    
    @field_validator('obtained_marks')
    @classmethod
    def validate_obtained_marks(cls, v: int, info) -> int:
        """Validate that obtained marks don't exceed total marks"""
        total_marks = info.data.get('total_marks')
        if total_marks and v > total_marks:
            raise ValueError(f'Obtained marks ({v}) cannot exceed total marks ({total_marks})')
        return v


class AppliedProgramSubmit(BaseModel):
    """Program application target information"""
    
    institute_id: UUID = Field(..., description="Institute ID")
    program_cycle_id: UUID = Field(..., description="Program admission cycle ID")
    preferred_campus_id: UUID = Field(..., description="Preferred campus ID")
    quota_id: UUID = Field(..., description="Quota ID to apply under")


class ApplicationSubmitRequest(BaseModel):
    """Complete application submission request"""
    
    student_profile: StudentProfileSubmit = Field(..., description="Student profile data")
    guardian: GuardianSubmit = Field(..., description="Guardian information")
    academic_record: AcademicRecordSubmit = Field(..., description="Academic record (Matric for now)")
    applied_programs: List[AppliedProgramSubmit] = Field(
        ..., 
        min_length=1,
        description="List of programs to apply to (at least one required)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
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
                        "program_cycle_id": "123e4567-e89b-12d3-a456-426614174001",
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

