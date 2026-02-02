from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.auth import User
from app.utils.auth import get_password_hash

dummy_router = APIRouter(
    prefix="/dummy",
    tags=["Super Admin - Dummy/Development Endpoints"],
)


class DummyUserCreate(BaseModel):
    """Dummy user creation - for development only"""
    email: EmailStr
    password: str
    is_super_admin: bool = False
    is_active: bool = True
    verified: bool = True


class DummyUserResponse(BaseModel):
    """Dummy user response"""
    id: UUID
    email: str
    is_super_admin: bool
    is_active: bool
    verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


@dummy_router.post("/register-user", response_model=DummyUserResponse, status_code=status.HTTP_201_CREATED)
def register_dummy_user(
    user_data: DummyUserCreate,
    db: Session = Depends(get_db),
):
    """
    Register a dummy user for development/testing.
    
    ⚠️ WARNING: This endpoint is for DEVELOPMENT ONLY.
    Remove or protect this endpoint in production.
    
    Creates a user with the specified credentials.
    Can create super admin users by setting is_super_admin=True.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email {user_data.email} already exists",
        )
    
    # Hash password
    hashed_password = get_password_hash(user_data.password)
    
    # Create user
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        is_super_admin=user_data.is_super_admin,
        is_active=user_data.is_active,
        verified=user_data.verified,
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@dummy_router.get("/users", response_model=List[DummyUserResponse])
def list_dummy_users(
    skip: int = 0,
    limit: int = 100,
    is_super_admin: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """
    List all users in the system.
    
    ⚠️ WARNING: This endpoint is for DEVELOPMENT ONLY.
    Remove or protect this endpoint in production.
    
    Useful for checking what users exist during development.
    """
    query = db.query(User)
    
    # Apply filters
    if is_super_admin is not None:
        query = query.filter(User.is_super_admin == is_super_admin)
    
    # Order by created_at
    query = query.order_by(User.created_at.desc())
    
    # Apply pagination
    users = query.offset(skip).limit(limit).all()
    
    return users
