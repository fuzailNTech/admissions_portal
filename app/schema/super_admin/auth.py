from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class SuperAdminLoginRequest(BaseModel):
    """Super admin login request"""
    email: EmailStr
    password: str


class SuperAdminLoginResponse(BaseModel):
    """Super admin login response"""
    user_id: UUID
    email: str
    access_token: str
    token_type: str = "bearer"
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


class SuperAdminMeResponse(BaseModel):
    """Super admin profile response"""
    id: UUID
    email: str
    is_super_admin: bool
    is_active: bool
    verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AssignInstituteAdminRequest(BaseModel):
    """Request to assign an institute admin"""
    user_id: UUID = Field(..., description="User ID to assign as admin")
    institute_id: UUID = Field(..., description="Institute to assign admin to")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: Optional[str] = None


class AssignInstituteAdminResponse(BaseModel):
    """Response after assigning institute admin"""
    staff_profile_id: UUID
    user_id: UUID
    institute_id: UUID
    first_name: str
    last_name: str
    role: str
    is_active: bool
    assigned_at: datetime
    
    class Config:
        from_attributes = True
