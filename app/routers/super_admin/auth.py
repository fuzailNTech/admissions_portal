from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt

from app.database.config.db import get_db
from app.database.models.auth import User
from app.schema.super_admin.auth import (
    SuperAdminLoginRequest,
    SuperAdminLoginResponse,
    SuperAdminMeResponse,
)
from app.utils.auth import (
    require_super_admin,
    verify_password,
    create_access_token,
)

super_admin_auth_router = APIRouter(
    prefix="/auth",
    tags=["Super Admin - Authentication"],
)


@super_admin_auth_router.post("/login", response_model=SuperAdminLoginResponse)
def super_admin_login(
    credentials: SuperAdminLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Super admin login endpoint.
    
    Only users with is_super_admin=True can login here.
    Returns JWT token for authentication.
    """
    # Find user by email
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Verify user is super admin
    if not user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Super admin privileges required.",
        )
    
    # Verify user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    
    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return SuperAdminLoginResponse(
        user_id=user.id,
        email=user.email,
        access_token=access_token,
        last_login=user.last_login_at,
        is_temporary_password=user.is_temporary_password,
    )


@super_admin_auth_router.get("/me", response_model=SuperAdminMeResponse)
def get_super_admin_profile(
    current_user: User = Depends(require_super_admin),
):
    """
    Get current super admin profile.
    
    Requires valid JWT token with super admin privileges.
    """
    return SuperAdminMeResponse(
        id=current_user.id,
        email=current_user.email,
        is_super_admin=current_user.is_super_admin,
        is_active=current_user.is_active,
        verified=current_user.verified,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )
