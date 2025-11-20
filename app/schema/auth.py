from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.database.models.auth import UserRole


class RegisterUser(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    verified: bool
    role: str
    institute_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True
