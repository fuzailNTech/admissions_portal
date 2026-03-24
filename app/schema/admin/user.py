from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.database.models.auth import StaffRoleType
from app.database.models.institute import CampusType


class AdminCreateUserRequest(BaseModel):
    email: EmailStr = Field(..., description="Login email for the staff user")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: StaffRoleType = Field(..., description="Staff role in the institute")
    phone_number: Optional[str] = Field(None, max_length=30)
    campus_ids: List[UUID] = Field(
        default_factory=list,
        description="Required for campus admins; must belong to the same institute",
    )
    is_active: bool = True


class AdminCreateUserResponse(BaseModel):
    user_id: UUID
    email: str
    message: str = "Staff user created. Login credentials have been sent to email."


class AdminUserUpdateRequest(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=30)
    role: Optional[StaffRoleType] = None
    campus_ids: Optional[List[UUID]] = Field(
        None,
        description="When provided, replaces all campus assignments for campus admins",
    )
    is_active: Optional[bool] = None
    verified: Optional[bool] = None


class AssignedCampusMetadata(BaseModel):
    id: UUID
    name: str
    campus_code: Optional[str] = None
    campus_type: CampusType
    city: Optional[str] = None
    is_active: bool


class AdminUserResponse(BaseModel):
    user_id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: StaffRoleType
    institute_id: UUID
    phone_number: Optional[str] = None
    is_active: bool
    verified: bool
    assigned_campuses: List[AssignedCampusMetadata] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
