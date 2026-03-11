import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.auth import User
from app.utils.auth import get_password_hash
from app.utils.smtp import send_mail_sync
from app import settings

logger = logging.getLogger(__name__)

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


class TestEmailRequest(BaseModel):
    """Request body for test email endpoint."""
    to_email: EmailStr


class EmailConfigDebug(BaseModel):
    """Debug view of mail config (passwords masked)."""
    MAIL_SERVER: Optional[str]
    MAIL_PORT: Optional[Any]  # int or "NOT_SET" / error message
    MAIL_FROM: Optional[str]
    MAIL_USERNAME: Optional[str]
    MAIL_USERNAME_set: bool
    MAIL_PASSWORD_set: bool
    MAIL_STARTTLS: bool
    MAIL_SSL_TLS: bool
    config_ok: bool
    config_error: Optional[str] = None


class TestEmailResponse(BaseModel):
    """Response from test email endpoint with debugging info."""
    success: bool
    message: str
    debug: dict


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


def _get_email_config_debug() -> dict:
    """Build debug info for mail settings (passwords masked)."""
    debug: dict = {}
    config_ok = True
    config_error = None

    try:
        debug["MAIL_SERVER"] = getattr(settings, "MAIL_SERVER", None)
        debug["MAIL_PORT"] = getattr(settings, "MAIL_PORT", None)
        debug["MAIL_FROM"] = getattr(settings, "MAIL_FROM", None)
        debug["MAIL_USERNAME"] = (
            f"{settings.MAIL_USERNAME[:3]}***" if settings.MAIL_USERNAME else None
        )
        debug["MAIL_USERNAME_set"] = bool(settings.MAIL_USERNAME)
        debug["MAIL_PASSWORD_set"] = bool(getattr(settings, "MAIL_PASSWORD", None))
        debug["MAIL_STARTTLS"] = getattr(settings, "MAIL_STARTTLS", None)
        debug["MAIL_SSL_TLS"] = getattr(settings, "MAIL_SSL_TLS", None)
    except Exception as e:
        config_ok = False
        config_error = str(e)
        logger.exception("Error reading mail config for debug")
        debug["config_error"] = config_error

    debug["config_ok"] = config_ok
    if config_error:
        debug["config_error"] = config_error
    return debug


@dummy_router.get("/email-config", response_model=EmailConfigDebug)
def get_email_config_debug():
    """
    Return current mail configuration for debugging (passwords never shown).

    Useful on Render to verify MAIL_* env vars are set and loaded.
    """
    try:
        port = getattr(settings, "MAIL_PORT", None)
    except Exception as e:
        port = f"ERROR: {e}"
    return EmailConfigDebug(
        MAIL_SERVER=getattr(settings, "MAIL_SERVER", None),
        MAIL_PORT=port,
        MAIL_FROM=getattr(settings, "MAIL_FROM", None),
        MAIL_USERNAME=(
            f"{settings.MAIL_USERNAME[:3]}***" if getattr(settings, "MAIL_USERNAME", None) else None
        ),
        MAIL_USERNAME_set=bool(getattr(settings, "MAIL_USERNAME", None)),
        MAIL_PASSWORD_set=bool(getattr(settings, "MAIL_PASSWORD", None)),
        MAIL_STARTTLS=getattr(settings, "MAIL_STARTTLS", False),
        MAIL_SSL_TLS=getattr(settings, "MAIL_SSL_TLS", False),
        config_ok=(
            bool(getattr(settings, "MAIL_SERVER", None))
            and getattr(settings, "MAIL_PORT", None) is not None
            and bool(getattr(settings, "MAIL_FROM", None))
        ),
        config_error=None,
    )


@dummy_router.post("/test-email", response_model=TestEmailResponse)
def test_email(request: TestEmailRequest):
    """
    Send a test email to the given address and return debug info.

    Use this to verify SMTP is working on Render (or locally).
    Returns success/failure and detailed debug (config snapshot, exception if any).
    """
    debug = _get_email_config_debug()
    logger.info("Test email requested to %s", request.to_email)

    if not debug.get("config_ok"):
        return TestEmailResponse(
            success=False,
            message="Mail config is incomplete or invalid. Check /dummy/email-config.",
            debug=debug,
        )

    subject = "[Admissions Portal] Test email"
    body = (
        "<p>This is a test email from the Admissions Portal.</p>"
        "<p>If you received this, SMTP is working.</p>"
    )
    try:
        logger.info("Attempting to send test email to %s via %s", request.to_email, debug.get("MAIL_SERVER"))
        send_mail_sync(
            recipients=request.to_email,
            subject=subject,
            body=body,
        )
        logger.info("Test email sent successfully to %s", request.to_email)
        debug["send_result"] = "sent"
        return TestEmailResponse(
            success=True,
            message=f"Test email sent to {request.to_email}.",
            debug=debug,
        )
    except Exception as e:
        logger.exception("Test email failed to %s: %s", request.to_email, e)
        debug["send_result"] = "failed"
        debug["send_error"] = str(e)
        debug["send_error_type"] = type(e).__name__
        return TestEmailResponse(
            success=False,
            message=f"Failed to send test email: {e}",
            debug=debug,
        )
