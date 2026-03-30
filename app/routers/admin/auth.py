import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.database.config.db import get_db
from app.database.models.auth import User, StaffProfile, PasswordResetToken
from app.schema.admin.auth import (
    AdminForgotPasswordRequest,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMeResponse,
    AdminResetPasswordRequest,
    PasswordResetMessageResponse,
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
from app.settings import PASSWORD_RESET_TOKEN_EXPIRE_MINUTES, ADMIN_PORTAL_URL
from app.utils.smtp import send_mail

admin_auth_router = APIRouter(prefix="/auth", tags=["Admin - Auth"])


def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@admin_auth_router.post("/forgot-password", response_model=PasswordResetMessageResponse)
def forgot_password(
    body: AdminForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    generic_response = PasswordResetMessageResponse()
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        return generic_response

    staff_profile = (
        db.query(StaffProfile).filter(StaffProfile.user_id == user.id).first()
    )
    if not staff_profile or not staff_profile.is_active:
        return generic_response

    now_utc = datetime.now(timezone.utc)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({PasswordResetToken.used_at: now_utc}, synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_reset_token(raw_token),
        expires_at=now_utc + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )
    db.add(reset_token)
    db.commit()

    reset_link = (
        f"{ADMIN_PORTAL_URL}/reset-password?token={raw_token}"
        if ADMIN_PORTAL_URL
        else ""
    )
    action_html = (
        f"<p><a href='{reset_link}'>Reset your password</a></p>"
        if reset_link
        else "<p>Reset link is currently unavailable. Please contact support.</p>"
    )
    body_html = (
        "<p>We received a password reset request for your admin account.</p>"
        + action_html
        + f"<p>This link will expire in {PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.</p>"
    )
    background_tasks.add_task(
        send_mail,
        user.email,
        "Admin password reset",
        body_html,
    )
    return generic_response


@admin_auth_router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    body: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
):
    now_utc = datetime.now(timezone.utc)
    token_hash = _hash_reset_token(body.token)
    reset_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )
    if (
        not reset_token
        or reset_token.used_at is not None
        or reset_token.expires_at < now_utc
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    staff_profile = (
        db.query(StaffProfile)
        .filter(StaffProfile.user_id == reset_token.user_id)
        .first()
    )
    if not staff_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token",
        )

    user.password_hash = get_password_hash(body.new_password)
    user.is_temporary_password = False
    reset_token.used_at = now_utc
    db.commit()


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

    # Check if user has staff profile (required for admin access)
    staff_profile = (
        db.query(StaffProfile).filter(StaffProfile.user_id == user.id).first()
    )

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

    On success, the password is set to permanent
     (is_temporary_password is set to False).
    """
    user = staff.user
    user.password_hash = get_password_hash(body.new_password)
    user.is_temporary_password = False
    db.commit()
