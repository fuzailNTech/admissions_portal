from typing import List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.config.db import get_db
from app.database.models.auth import StaffCampus, StaffProfile, StaffRoleType, User
from app.database.models.institute import Campus
from app.schema.admin.user import (
    AdminCreateUserRequest,
    AdminCreateUserResponse,
    AssignedCampusMetadata,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from app.utils.auth import generate_strong_password, get_password_hash, is_institute_admin
from app.utils.smtp import send_mail

admin_user_router = APIRouter(
    prefix="/users",
    tags=["Admin - User Management"],
)


def _ensure_campuses_in_institute(
    campus_ids: List[UUID],
    institute_id: UUID,
    db: Session,
) -> List[Campus]:
    if not campus_ids:
        return []
    campuses = (
        db.query(Campus)
        .filter(Campus.id.in_(campus_ids), Campus.institute_id == institute_id)
        .all()
    )
    if len(campuses) != len(set(campus_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more campus_ids are invalid for this institute",
        )
    return campuses


def _build_admin_user_response(staff: StaffProfile) -> AdminUserResponse:
    assigned_campuses = [
        AssignedCampusMetadata(
            id=assignment.campus.id,
            name=assignment.campus.name,
            campus_code=assignment.campus.campus_code,
            campus_type=assignment.campus.campus_type,
            city=assignment.campus.city,
            is_active=assignment.campus.is_active,
        )
        for assignment in staff.campus_assignments
        if assignment.is_active and assignment.campus is not None
    ]
    return AdminUserResponse(
        user_id=staff.user.id,
        email=staff.user.email,
        first_name=staff.first_name,
        last_name=staff.last_name,
        role=staff.role,
        institute_id=staff.institute_id,
        phone_number=staff.phone_number,
        is_active=staff.is_active,
        verified=staff.user.verified,
        assigned_campuses=assigned_campuses,
        created_at=staff.created_at,
        updated_at=staff.updated_at,
    )


@admin_user_router.post("", response_model=AdminCreateUserResponse, status_code=status.HTTP_201_CREATED)
def create_staff_user(
    body: AdminCreateUserRequest,
    background_tasks: BackgroundTasks,
    current_staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    if body.role == StaffRoleType.CAMPUS_ADMIN and not body.campus_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="campus_ids are required for campus admin users",
        )

    if body.role == StaffRoleType.INSTITUTE_ADMIN and body.campus_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="campus_ids are not allowed for institute admin users",
        )

    _ensure_campuses_in_institute(body.campus_ids, current_staff.institute_id, db)
    temp_password = generate_strong_password()

    user = User(
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        password_hash=get_password_hash(temp_password),
        is_temporary_password=True,
        verified=True,
        is_super_admin=False,
        is_active=True,
    )
    db.add(user)
    db.flush()

    staff_profile = StaffProfile(
        user_id=user.id,
        first_name=body.first_name,
        last_name=body.last_name,
        phone_number=body.phone_number,
        role=body.role,
        institute_id=current_staff.institute_id,
        is_active=body.is_active,
        assigned_by=current_staff.user_id,
    )
    db.add(staff_profile)
    db.flush()

    if body.role == StaffRoleType.CAMPUS_ADMIN:
        for campus_id in body.campus_ids:
            db.add(
                StaffCampus(
                    staff_profile_id=staff_profile.id,
                    campus_id=campus_id,
                    is_active=True,
                )
            )

    db.commit()

    body_html = (
        "<p>Your staff account has been created.</p>"
        "<p>Use the credentials below to log in:</p>"
        f"<p><strong>Email:</strong> {body.email}</p>"
        f"<p><strong>Password:</strong> {temp_password}</p>"
        "<p>Please change your password after first login.</p>"
    )
    background_tasks.add_task(
        send_mail,
        body.email,
        "Your staff login credentials",
        body_html,
    )

    return AdminCreateUserResponse(user_id=user.id, email=user.email)


@admin_user_router.get("", response_model=List[AdminUserResponse])
def list_staff_users(
    current_staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    staff_users = (
        db.query(StaffProfile)
        .filter(
            StaffProfile.institute_id == current_staff.institute_id,
            StaffProfile.user_id != current_staff.user_id,
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_build_admin_user_response(staff) for staff in staff_users]


@admin_user_router.get("/{user_id}", response_model=AdminUserResponse)
def get_staff_user(
    user_id: UUID,
    current_staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    staff_user = (
        db.query(StaffProfile)
        .filter(
            StaffProfile.user_id == user_id,
            StaffProfile.institute_id == current_staff.institute_id,
        )
        .first()
    )
    if not staff_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff user not found")
    return _build_admin_user_response(staff_user)


@admin_user_router.patch("/{user_id}", response_model=AdminUserResponse)
def update_staff_user(
    user_id: UUID,
    body: AdminUserUpdateRequest,
    current_staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_staff.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot update yourself from this endpoint",
        )

    staff_user = (
        db.query(StaffProfile)
        .filter(
            StaffProfile.user_id == user_id,
            StaffProfile.institute_id == current_staff.institute_id,
        )
        .first()
    )
    if not staff_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff user not found")

    if body.role == StaffRoleType.CAMPUS_ADMIN and body.campus_ids is not None and len(body.campus_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="campus_ids cannot be empty for campus admin users",
        )

    if body.role == StaffRoleType.INSTITUTE_ADMIN and body.campus_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="campus_ids are not allowed for institute admin users",
        )

    if body.first_name is not None:
        staff_user.first_name = body.first_name
        staff_user.user.first_name = body.first_name
    if body.last_name is not None:
        staff_user.last_name = body.last_name
        staff_user.user.last_name = body.last_name
    if body.phone_number is not None:
        staff_user.phone_number = body.phone_number
    if body.role is not None:
        staff_user.role = body.role
    if body.is_active is not None:
        staff_user.is_active = body.is_active
    if body.verified is not None:
        staff_user.user.verified = body.verified

    effective_role = body.role if body.role is not None else staff_user.role
    if effective_role == StaffRoleType.CAMPUS_ADMIN and body.campus_ids is not None:
        _ensure_campuses_in_institute(body.campus_ids, current_staff.institute_id, db)
        db.query(StaffCampus).filter(StaffCampus.staff_profile_id == staff_user.id).delete()
        for campus_id in body.campus_ids:
            db.add(
                StaffCampus(
                    staff_profile_id=staff_user.id,
                    campus_id=campus_id,
                    is_active=True,
                )
            )
    if effective_role == StaffRoleType.INSTITUTE_ADMIN:
        db.query(StaffCampus).filter(StaffCampus.staff_profile_id == staff_user.id).delete()

    db.commit()
    db.refresh(staff_user)
    return _build_admin_user_response(staff_user)


@admin_user_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_staff_user(
    user_id: UUID,
    current_staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_staff.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    staff_user = (
        db.query(StaffProfile)
        .filter(
            StaffProfile.user_id == user_id,
            StaffProfile.institute_id == current_staff.institute_id,
        )
        .first()
    )
    if not staff_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff user not found")

    db.delete(staff_user.user)
    db.commit()
