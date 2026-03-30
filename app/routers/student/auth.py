import hashlib
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import secrets

from app.database.config.db import get_db
from app.database.models.auth import User, PasswordResetToken
from app.database.models.student import (
    StudentProfile,
    StudentGuardian,
    StudentAcademicRecord,
    AcademicLevel,
)
from app.database.models.application import UploadToken
from app.schema.student.auth import (
    PasswordResetMessageResponse,
    StudentForgotPasswordRequest,
    StudentLoginRequest,
    StudentLoginResponse,
    StudentResetPasswordRequest,
    StudentUpdatePasswordRequest,
    StudentMeResponse,
    StudentProfileMe,
    GuardianMe,
    AcademicRecordMe,
    StudentMeUpdateRequest,
    StudentDocumentsUploadUrlsRequest,
    StudentDocumentsUploadUrlsResponse,
    UploadUrlItem,
)
from app import s3 as s3_module
from app.utils.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_student,
)
from app.settings import PASSWORD_RESET_TOKEN_EXPIRE_MINUTES, STUDENT_PORTAL_URL
from app.utils.smtp import send_mail

student_auth_router = APIRouter(prefix="/auth", tags=["Student - Auth"])
ME_DOCUMENT_VIEW_TTL_SECONDS = 900


def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@student_auth_router.post(
    "/forgot-password", response_model=PasswordResetMessageResponse
)
def forgot_password(
    body: StudentForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    generic_response = PasswordResetMessageResponse()
    student_profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.identity_doc_number == body.identity_doc_number.strip())
        .first()
    )
    if not student_profile:
        return generic_response

    user = db.query(User).filter(User.id == student_profile.user_id).first()
    if not user:
        return generic_response

    recipient_email = (student_profile.primary_email or user.email or "").strip()
    if not recipient_email:
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
        f"{STUDENT_PORTAL_URL}/reset-password?token={raw_token}"
        if STUDENT_PORTAL_URL
        else ""
    )
    action_html = (
        f"<p><a href='{reset_link}'>Reset your password</a></p>"
        if reset_link
        else "<p>Reset link is currently unavailable. Please contact support.</p>"
    )
    body_html = (
        "<p>We received a password reset request for your student account.</p>"
        + action_html
        + f"<p>This token will expire in {PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.</p>"
    )
    background_tasks.add_task(
        send_mail,
        recipient_email,
        "Student password reset",
        body_html,
    )
    return generic_response


@student_auth_router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    body: StudentResetPasswordRequest,
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

    student_profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == reset_token.user_id)
        .first()
    )
    if not student_profile:
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
    user.password_hash = get_password_hash(body.new_password)
    user.is_temporary_password = False
    db.commit()


def _get_secondary_academic_record(student: StudentProfile):
    """Return the SECONDARY (Matric/SSC) academic record if present."""
    for r in student.academic_records:
        if r.level == AcademicLevel.SECONDARY:
            return r
    return None


def _build_student_profile_me_with_view_urls(
    student: StudentProfile,
) -> StudentProfileMe:
    profile_data = StudentProfileMe.model_validate(student).model_dump()
    profile_data["profile_picture_url"] = (
        s3_module.build_presigned_get_from_object_url_or_key(
            student.profile_picture_url, expires_in=ME_DOCUMENT_VIEW_TTL_SECONDS
        )
        or ""
    )
    profile_data["identity_doc_url"] = (
        s3_module.build_presigned_get_from_object_url_or_key(
            student.identity_doc_url, expires_in=ME_DOCUMENT_VIEW_TTL_SECONDS
        )
        or ""
    )
    return StudentProfileMe.model_validate(profile_data)


def _build_academic_record_me_with_view_url(
    academic_record: StudentAcademicRecord | None,
) -> AcademicRecordMe | None:
    if academic_record is None:
        return None
    academic_data = AcademicRecordMe.model_validate(academic_record).model_dump()
    academic_data["result_card_url"] = (
        s3_module.build_presigned_get_from_object_url_or_key(
            academic_record.result_card_url, expires_in=ME_DOCUMENT_VIEW_TTL_SECONDS
        )
        or ""
    )
    return AcademicRecordMe.model_validate(academic_data)


@student_auth_router.get("/me", response_model=StudentMeResponse)
def get_current_student_me(
    student: StudentProfile = Depends(get_current_student),
):
    """
    Get current authenticated student's profile with guardian and academic record (SECONDARY only).
    """
    guardian = (
        GuardianMe.model_validate(student.guardians[0]) if student.guardians else None
    )
    sec_record = _get_secondary_academic_record(student)
    return StudentMeResponse(
        student_profile=_build_student_profile_me_with_view_urls(student),
        guardian=guardian,
        academic_record=_build_academic_record_me_with_view_url(sec_record),
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
    Document updates are supported using upload_token + pending document URLs from
    POST /auth/me/documents/upload-urls.
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

    wants_profile_picture = body.profile_picture_url is not None
    wants_identity_doc = body.identity_doc_url is not None
    wants_result_card = body.result_card_url is not None
    wants_any_document_update = (
        wants_profile_picture or wants_identity_doc or wants_result_card
    )

    pending_keys_to_cleanup = []
    if wants_any_document_update:
        if not s3_module.get_bucket():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document upload is not configured",
            )
        if not body.upload_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="upload_token is required when updating document URLs",
            )
        now_utc = datetime.now(timezone.utc)
        upload_token_row = (
            db.query(UploadToken).filter(UploadToken.token == body.upload_token).first()
        )
        if (
            not upload_token_row
            or upload_token_row.expires_at < now_utc
            or upload_token_row.used_at
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired upload token",
            )

        pending_prefix = f"uploads/pending/{body.upload_token}"
        expected_profile_url = s3_module.object_url(
            f"{pending_prefix}/profile_picture.jpg"
        )
        expected_identity_url = s3_module.object_url(
            f"{pending_prefix}/identity_document.jpg"
        )
        expected_result_url = s3_module.object_url(
            f"{pending_prefix}/academic_result_card.pdf"
        )

        student_prefix = f"students/{student.id}"

        if wants_profile_picture:
            if body.profile_picture_url != expected_profile_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid profile picture URL for this upload token",
                )
            s3_module.delete_objects([f"{student_prefix}/profile/profile.png"])
            s3_module.copy_object(
                f"{pending_prefix}/profile_picture.jpg",
                f"{student_prefix}/profile/profile.png",
            )
            student.profile_picture_url = f"{student_prefix}/profile/profile.png"
            pending_keys_to_cleanup.append(f"{pending_prefix}/profile_picture.jpg")

        if wants_identity_doc:
            if body.identity_doc_url != expected_identity_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid identity document URL for this upload token",
                )
            s3_module.delete_objects([f"{student_prefix}/identity/document.jpg"])
            s3_module.copy_object(
                f"{pending_prefix}/identity_document.jpg",
                f"{student_prefix}/identity/document.jpg",
            )
            student.identity_doc_url = f"{student_prefix}/identity/document.jpg"
            pending_keys_to_cleanup.append(f"{pending_prefix}/identity_document.jpg")

        if wants_result_card:
            if body.result_card_url != expected_result_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid result card URL for this upload token",
                )
            target_academic_record = academic_record_obj
            if target_academic_record is None:
                target_academic_record = (
                    db.query(StudentAcademicRecord)
                    .filter(
                        StudentAcademicRecord.student_profile_id == student.id,
                        StudentAcademicRecord.level == AcademicLevel.SECONDARY,
                    )
                    .first()
                )
            if target_academic_record is not None:
                s3_module.delete_objects(
                    [
                        f"{student_prefix}/academic/{target_academic_record.id}/result_card.pdf"
                    ]
                )
                s3_module.copy_object(
                    f"{pending_prefix}/academic_result_card.pdf",
                    f"{student_prefix}/academic/{target_academic_record.id}/result_card.pdf",
                )
                target_academic_record.result_card_url = f"{student_prefix}/academic/{target_academic_record.id}/result_card.pdf"
                pending_keys_to_cleanup.append(
                    f"{pending_prefix}/academic_result_card.pdf"
                )
                if academic_record_obj is None:
                    academic_record_obj = target_academic_record

        upload_token_row.used_at = now_utc
        db.add(upload_token_row)

    db.commit()
    db.refresh(student)
    if pending_keys_to_cleanup:
        try:
            s3_module.delete_objects(pending_keys_to_cleanup)
        except Exception:
            pass

    if guardian_obj is not None:
        guardian = GuardianMe.model_validate(guardian_obj)
    else:
        first_guardian = (
            db.query(StudentGuardian)
            .filter(StudentGuardian.student_profile_id == student.id)
            .first()
        )
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
        student_profile=_build_student_profile_me_with_view_urls(student),
        guardian=guardian,
        academic_record=_build_academic_record_me_with_view_url(sec_record),
    )


@student_auth_router.post(
    "/me/documents/upload-urls",
    response_model=StudentDocumentsUploadUrlsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get presigned upload URLs for student profile documents",
)
def get_student_document_upload_urls(
    body: StudentDocumentsUploadUrlsRequest,
    student: StudentProfile = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Return short-lived presigned PUT URLs for profile picture, identity document,
    and secondary academic result card for the authenticated student.
    """
    if not s3_module.get_bucket():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document upload is not configured",
        )

    token_str = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    upload_token = UploadToken(token=token_str, expires_at=expires_at)
    db.add(upload_token)
    db.commit()

    prefix = f"uploads/pending/{token_str}"
    keys = {
        "profile_picture": f"{prefix}/profile_picture.jpg",
        "identity_document": f"{prefix}/identity_document.jpg",
        "academic_result_card": f"{prefix}/academic_result_card.pdf",
    }

    return StudentDocumentsUploadUrlsResponse(
        upload_token=token_str,
        profile_picture=UploadUrlItem(
            upload_url=s3_module.generate_presigned_put(
                keys["profile_picture"],
                content_type=body.profile_picture_content_type,
            ),
            object_url=s3_module.object_url(keys["profile_picture"]),
            content_type=body.profile_picture_content_type,
        ),
        identity_document=UploadUrlItem(
            upload_url=s3_module.generate_presigned_put(
                keys["identity_document"],
                content_type=body.identity_document_content_type,
            ),
            object_url=s3_module.object_url(keys["identity_document"]),
            content_type=body.identity_document_content_type,
        ),
        academic_result_card=UploadUrlItem(
            upload_url=s3_module.generate_presigned_put(
                keys["academic_result_card"],
                content_type=body.result_card_content_type,
            ),
            object_url=s3_module.object_url(keys["academic_result_card"]),
            content_type=body.result_card_content_type,
        ),
    )
