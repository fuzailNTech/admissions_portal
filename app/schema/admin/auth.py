from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.database.models.auth import StaffRoleType


class AdminUpdatePasswordRequest(BaseModel):
    """Request to update admin password (current + new)."""
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class AdminLoginRequest(BaseModel):
    """Admin login request."""
    email: EmailStr
    password: str


class AdminLoginResponse(BaseModel):
    """Admin login response for staff members."""
    user_id: UUID
    token: str
    role: StaffRoleType  # Staff role (INSTITUTE_ADMIN or CAMPUS_ADMIN)
    last_login: datetime
    is_temporary_password: bool = False

    class Config:
        from_attributes = True


class StaffInfo(BaseModel):
    """Staff profile information."""
    id: UUID
    first_name: str
    last_name: str
    phone_number: Optional[str]
    profile_picture_url: Optional[str]
    role: StaffRoleType
    institute_id: UUID
    is_active: bool
    
    class Config:
        from_attributes = True


class AdminMeResponse(BaseModel):
    """Current admin (staff) user information."""
    user_id: UUID
    email: str
    is_active: bool
    verified: bool
    last_login: Optional[datetime]
    created_at: datetime
    staff_profile: StaffInfo  # Staff profile (always present for admin endpoints)
    
    class Config:
        from_attributes = True
