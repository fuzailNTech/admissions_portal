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
    is_temporary_password: bool = False

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


