from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.auth import User, StaffProfile
from app.schema.super_admin.user import CreateUserRequest, CreateUserResponse, UserResponse, UserUpdateRequest
from app.utils.auth import require_super_admin, get_password_hash, generate_strong_password
from app.utils.smtp import send_mail

users_router = APIRouter(
    prefix="/users",
    tags=["Super Admin - User Management"],
)


@users_router.post("", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    request: CreateUserRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Create a user. A random password is generated and sent to the provided email.
    """
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )
    password = generate_strong_password()
    user = User(
        email=request.email,
        first_name=request.first_name,
        last_name=request.last_name,
        password_hash=get_password_hash(password),
        is_temporary_password=True,
        verified=False,
        is_super_admin=request.is_super_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    body_html = (
        "<p>Your account has been created.</p>"
        "<p>Use the credentials below to log in:</p>"
        f"<p><strong>Email:</strong> {request.email}</p>"
        f"<p><strong>Password:</strong> {password}</p>"
        "<p>Please change your password after your first login.</p>"
    )
    background_tasks.add_task(
        send_mail,
        request.email,
        "Your login credentials",
        body_html,
    )

    return CreateUserResponse(
        user_id=user.id,
        email=user.email,
    )


@users_router.get("", response_model=List[UserResponse])
def list_users(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    List users with optional pagination. Excludes the logged-in user.
    """
    users = (
        db.query(User)
        .filter(User.id != current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [UserResponse.model_validate(u) for u in users]


@users_router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Get a single user by ID.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@users_router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    body: UserUpdateRequest,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Update a user. Only first_name, last_name, is_super_admin, verified, and is_active can be updated.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a user. Fails if the user is bound to any institute (has a staff profile).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    staff_profile = db.query(StaffProfile).filter(StaffProfile.user_id == user_id).first()
    if staff_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete user: user is bound to an institute",
        )
    db.delete(user)
    db.commit()
