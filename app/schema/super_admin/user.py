from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class CreateUserRequest(BaseModel):
    """Request to create a user. Password is generated and sent to email."""
    email: EmailStr = Field(..., description="User email (login and credentials delivery)")
    first_name: str = Field(..., min_length=1, max_length=100, description="User first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="User last name")
    is_super_admin: bool = Field(False, description="Whether the user is a super admin")


class CreateUserResponse(BaseModel):
    """Response after creating a user."""
    user_id: UUID
    email: str
    message: str = "User created. Login credentials have been sent to the email address."

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    """Partial update for a user. Only provided fields are updated."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_super_admin: Optional[bool] = None
    verified: Optional[bool] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """User details for GET response."""
    id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_super_admin: bool
    is_active: bool
    verified: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True
