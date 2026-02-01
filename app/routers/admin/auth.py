from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.config.db import get_db
from app.database.models.auth import User, StaffProfile
from app.schema.admin.auth import AdminLoginRequest, AdminLoginResponse, AdminMeResponse, StaffInfo
from app.utils.auth import (
    verify_password,
    create_access_token,
    get_current_user,
)

admin_auth_router = APIRouter(prefix="/auth", tags=["Admin - Auth"])


@admin_auth_router.post("/login", response_model=AdminLoginResponse)
def admin_login(
    body: AdminLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Admin login endpoint for staff members (Institute Admin, Campus Admin).
        
    Returns:
        - user_id: UUID of the user
        - token: JWT access token
        - role: Staff role (INSTITUTE_ADMIN or CAMPUS_ADMIN)
        - last_login: Last login timestamp
    """
    # Get user by email
    user = db.query(User).filter(User.email == body.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Verify password
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Check if user is verified
    if not user.verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not verified",
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Check if user has staff profile (required for admin access)
    staff_profile = db.query(StaffProfile).filter(
        StaffProfile.user_id == user.id
    ).first()
    
    if not staff_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have staff access",
        )
    
    if not staff_profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff profile is inactive",
        )

    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})

    return AdminLoginResponse(
        user_id=user.id,
        token=access_token,
        role=staff_profile.role,
        last_login=user.last_login_at,
    )


@admin_auth_router.get("/me", response_model=AdminMeResponse)
def get_current_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current authenticated admin (staff) user information.
    
    
    Returns full user details including staff profile.
    """
    # Verify user has staff profile
    staff_profile = db.query(StaffProfile).filter(
        StaffProfile.user_id == current_user.id
    ).first()
    
    if not staff_profile or not staff_profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have staff access",
        )

    # Build staff info
    staff_info = StaffInfo(
        id=staff_profile.id,
        first_name=staff_profile.first_name,
        last_name=staff_profile.last_name,
        phone_number=staff_profile.phone_number,
        profile_picture_url=staff_profile.profile_picture_url,
        role=staff_profile.role,
        institute_id=staff_profile.institute_id,
        is_active=staff_profile.is_active,
    )

    return AdminMeResponse(
        user_id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        verified=current_user.verified,
        last_login=current_user.last_login_at,
        created_at=current_user.created_at,
        staff_profile=staff_info,
    )
