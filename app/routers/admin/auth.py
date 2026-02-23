from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.config.db import get_db
from app.database.models.auth import User, StaffProfile
from app.schema.admin.auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMeResponse,
    AdminUpdatePasswordRequest,
    StaffInfo,
)
from app.utils.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    get_current_staff,
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
        is_temporary_password=user.is_temporary_password,
    )


@admin_auth_router.get("/me", response_model=AdminMeResponse)
def get_current_admin(
    staff: StaffProfile = Depends(get_current_staff),
):
    """
    Get current authenticated admin (staff) user information.

    Returns full user details including staff profile.
    """
    user = staff.user
    staff_info = StaffInfo(
        id=staff.id,
        first_name=staff.first_name,
        last_name=staff.last_name,
        phone_number=staff.phone_number,
        profile_picture_url=staff.profile_picture_url,
        role=staff.role,
        institute_id=staff.institute_id,
        is_active=staff.is_active,
    )
    return AdminMeResponse(
        user_id=user.id,
        email=user.email,
        is_active=user.is_active,
        verified=user.verified,
        last_login=user.last_login_at,
        created_at=user.created_at,
        staff_profile=staff_info,
    )


@admin_auth_router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def update_password(
    body: AdminUpdatePasswordRequest,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Update the authenticated admin's password.

    Requires current password. On success, the password is set to permanent
    (is_temporary_password is set to False).
    """
    user = staff.user
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    user.password_hash = get_password_hash(body.new_password)
    user.is_temporary_password = False
    db.commit()
