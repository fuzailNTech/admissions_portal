from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt

from app.database.config.db import get_db
from app.database.models.auth import User, StaffProfile
from app.database.models.auth import StaffRoleType
from app.schema.super_admin.auth import (
    SuperAdminLoginRequest,
    SuperAdminLoginResponse,
    SuperAdminMeResponse,
    AssignInstituteAdminRequest,
    AssignInstituteAdminResponse,
)
from app.utils.auth import (
    get_current_user,
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


@super_admin_auth_router.post(
    "/assign-institute-admin",
    response_model=AssignInstituteAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_institute_admin(
    assignment: AssignInstituteAdminRequest,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Assign a user as institute admin.
    
    Creates a StaffProfile with INSTITUTE_ADMIN role.
    Only super admins can perform this action.
    """
    # Verify user exists
    user = db.query(User).filter(User.id == assignment.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Verify user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign inactive user as admin",
        )
    
    # Verify institute exists
    from app.database.models.institute import Institute
    institute = db.query(Institute).filter(Institute.id == assignment.institute_id).first()
    if not institute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institute not found",
        )
    
    # Check if user already has a staff profile
    existing_profile = db.query(StaffProfile).filter(
        StaffProfile.user_id == assignment.user_id
    ).first()
    
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User already has a staff profile at institute: {existing_profile.institute.name}",
        )
    
    # Create staff profile
    staff_profile = StaffProfile(
        user_id=assignment.user_id,
        first_name=assignment.first_name,
        last_name=assignment.last_name,
        phone_number=assignment.phone_number,
        role=StaffRoleType.INSTITUTE_ADMIN,
        institute_id=assignment.institute_id,
        is_active=True,
        assigned_by=current_user.id,
    )
    
    db.add(staff_profile)
    db.commit()
    db.refresh(staff_profile)
    
    return AssignInstituteAdminResponse(
        staff_profile_id=staff_profile.id,
        user_id=staff_profile.user_id,
        institute_id=staff_profile.institute_id,
        first_name=staff_profile.first_name,
        last_name=staff_profile.last_name,
        role=staff_profile.role.value,
        is_active=staff_profile.is_active,
        assigned_at=staff_profile.assigned_at,
    )
