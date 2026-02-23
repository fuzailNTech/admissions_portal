from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.config.db import get_db
from app.database.models.auth import User
from app.database.models.student import StudentProfile, StudentGuardian, StudentAcademicRecord, AcademicLevel
from app.schema.student.auth import (
    StudentLoginRequest,
    StudentLoginResponse,
    StudentUpdatePasswordRequest,
    StudentMeResponse,
    StudentProfileMe,
    GuardianMe,
    AcademicRecordMe,
    StudentMeUpdateRequest,
)
from app.utils.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_student,
)

student_auth_router = APIRouter(prefix="/auth", tags=["Student - Auth"])


@student_auth_router.post("/login", response_model=StudentLoginResponse)
def student_login(
    body: StudentLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Student login via identity document number (CNIC / B-Form) and password.

    Returns user_id, token, last_login, and is_temporary_password.
    """
    # Find student profile by identity_doc_number
    student_profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.identity_doc_number == body.identity_doc_number.strip())
        .first()
    )
    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid identity document number or password",
        )

    user = db.query(User).filter(User.id == student_profile.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid identity document number or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid identity document number or password",
        )

    user.last_login_at = datetime.utcnow()
    db.commit()

    access_token = create_access_token(data={"sub": str(user.id)})

    return StudentLoginResponse(
        user_id=user.id,
        token=access_token,
        last_login=user.last_login_at,
        is_temporary_password=user.is_temporary_password,
    )


@student_auth_router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def update_password(
    body: StudentUpdatePasswordRequest,
    student: StudentProfile = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Update the authenticated student's password.

    Requires current password. On success, the password is set to permanent
    (is_temporary_password is set to False).
    """
    user = student.user
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    user.password_hash = get_password_hash(body.new_password)
    user.is_temporary_password = False
    db.commit()


def _get_secondary_academic_record(student: StudentProfile):
    """Return the SECONDARY (Matric/SSC) academic record if present."""
    for r in student.academic_records:
        if r.level == AcademicLevel.SECONDARY:
            return r
    return None


@student_auth_router.get("/me", response_model=StudentMeResponse)
def get_current_student_me(
    student: StudentProfile = Depends(get_current_student),
):
    """
    Get current authenticated student's profile with guardian and academic record (SECONDARY only).
    """
    guardian = GuardianMe.model_validate(student.guardians[0]) if student.guardians else None
    sec_record = _get_secondary_academic_record(student)
    return StudentMeResponse(
        student_profile=StudentProfileMe.model_validate(student),
        guardian=guardian,
        academic_record=AcademicRecordMe.model_validate(sec_record) if sec_record else None,
    )


@student_auth_router.patch("/me", response_model=StudentMeResponse)
def update_current_student_me(
    body: StudentMeUpdateRequest,
    student: StudentProfile = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Update the authenticated student's profile, guardian, and/or academic record.
    When updating guardian or academic_record, include their id (from GET /me) inside the object.
    Only provided sections are applied. Document URLs are not accepted here; use documents endpoint.
    """
    if body.student_profile is not None:
        update_data = body.student_profile.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(student, key, value)

    guardian_obj = None
    if body.guardian is not None:
        guardian_obj = (
            db.query(StudentGuardian)
            .filter(
                StudentGuardian.id == body.guardian.id,
                StudentGuardian.student_profile_id == student.id,
            )
            .first()
        )
        if guardian_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guardian not found or does not belong to your profile",
            )
        update_data = body.guardian.model_dump(exclude_unset=True)
        update_data.pop("id", None)
        for key, value in update_data.items():
            setattr(guardian_obj, key, value)

    academic_record_obj = None
    if body.academic_record is not None:
        academic_record_obj = (
            db.query(StudentAcademicRecord)
            .filter(
                StudentAcademicRecord.id == body.academic_record.id,
                StudentAcademicRecord.student_profile_id == student.id,
            )
            .first()
        )
        if academic_record_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Academic record not found or does not belong to your profile",
            )
        update_data = body.academic_record.model_dump(exclude_unset=True)
        update_data.pop("id", None)
        for key, value in update_data.items():
            setattr(academic_record_obj, key, value)

    db.commit()
    db.refresh(student)

    if guardian_obj is not None:
        guardian = GuardianMe.model_validate(guardian_obj)
    else:
        first_guardian = db.query(StudentGuardian).filter(StudentGuardian.student_profile_id == student.id).first()
        guardian = GuardianMe.model_validate(first_guardian) if first_guardian else None
    if academic_record_obj is not None:
        sec_record = academic_record_obj
    else:
        sec_record = (
            db.query(StudentAcademicRecord)
            .filter(
                StudentAcademicRecord.student_profile_id == student.id,
                StudentAcademicRecord.level == AcademicLevel.SECONDARY,
            )
            .first()
        )
    return StudentMeResponse(
        student_profile=StudentProfileMe.model_validate(student),
        guardian=guardian,
        academic_record=AcademicRecordMe.model_validate(sec_record) if sec_record else None,
    )
