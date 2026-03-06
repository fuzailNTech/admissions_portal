"""
Admin application list endpoint.
Institute admin: all applications of their institute.
Campus admin: applications at their preferred campus(es) OR assigned to them.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database.config.db import get_db
from app.database.models.admission import (
    AdmissionCycle,
    AdmissionCycleStatus,
    CampusAdmissionCycle,
    ProgramAdmissionCycle,
    ProgramQuota,
    QuotaType,
)
from app.database.models.application import (
    Application,
    ApplicationComment,
    ApplicationDocument,
    ApplicationLogHistory,
    ApplicationSnapshot,
    ApplicationStatus,
    DocumentType,
    StudentComment,
    VerificationStatus,
)
from app.database.models.auth import StaffProfile, StaffRoleType
from app.database.models.workflow import WorkflowInstance, WorkflowInstanceStep, WorkflowStepStatus
from app.schema.admin.application import (
    ApplicationDetailResponse,
    ApplicationListItem,
    ApplicationListStudentSummary,
    CompleteTaskRequest,
    PaginatedApplicationListResponse,
    GuardianDetail,
    AcademicRecordDetail,
    ApplicationCommentItem,
    ApplicationDocumentItem,
    StaffCommentCreate,
    DocumentRequestCreate,
    DocumentVerificationUpdate,
    WorkflowStepItem,
)
from app.utils.auth import require_admin_staff, get_accessible_campuses
from app.utils.engine import complete_user_task_and_persist

application_router = APIRouter(prefix="/applications", tags=["Admin - Applications"])


def _can_access_application(app: Application, current_staff: StaffProfile, db: Session) -> bool:
    """True if current_staff is allowed to access this application (RBAC)."""
    if app.institute_id != current_staff.institute_id:
        return False
    if current_staff.role == StaffRoleType.INSTITUTE_ADMIN:
        return True
    if current_staff.role == StaffRoleType.CAMPUS_ADMIN:
        if app.assigned_to == current_staff.id:
            return True
        accessible = get_accessible_campuses(current_staff, db)
        return app.preferred_campus_id in [c.id for c in accessible]
    return False


@application_router.get(
    "",
    response_model=PaginatedApplicationListResponse,
    summary="List applications (admin)",
)
def list_applications(
    current_staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
    admission_cycle_id: Optional[UUID] = Query(None, description="Filter by admission cycle (default: current open cycle)"),
    preferred_campus_id: Optional[UUID] = Query(None, description="Filter by preferred campus"),
    program_id: Optional[UUID] = Query(None, description="Filter by program"),
    quota: Optional[QuotaType] = Query(None, description="Filter by quota type (e.g. open_merit, hafiz_e_quran)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by application status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """
    List applications for the current admin.

    By default, only applications from the **current open admission cycle** are returned.
    Pass `admission_cycle_id` to view a specific cycle (e.g. past cycles).

    - **Institute admin:** sees all applications of their institute (within the cycle).
    - **Campus admin:** sees applications where preferred_campus is one of their assigned campuses, OR application is assigned to them.
    """
    # Resolve effective admission cycle: use param if provided, else current open cycle for institute
    effective_cycle_id = admission_cycle_id
    if effective_cycle_id is None:
        open_cycle = (
            db.query(AdmissionCycle)
            .filter(
                AdmissionCycle.institute_id == current_staff.institute_id,
                AdmissionCycle.status == AdmissionCycleStatus.OPEN,
            )
            .order_by(AdmissionCycle.application_end_date.desc())
            .first()
        )
        effective_cycle_id = open_cycle.id if open_cycle else None

    # If no cycle (none passed and no open cycle), return empty list with total 0
    if effective_cycle_id is None:
        return PaginatedApplicationListResponse(items=[], total=0)

    query = (
        db.query(Application)
        .options(
            joinedload(Application.snapshot),
            joinedload(Application.preferred_campus),
            joinedload(Application.preferred_program_cycle).joinedload(ProgramAdmissionCycle.program),
            joinedload(Application.quota),
            joinedload(Application.assigned_staff),
        )
        .join(Application.preferred_program_cycle)
        .join(ProgramAdmissionCycle.campus_admission_cycle)
        .filter(
            Application.institute_id == current_staff.institute_id,
            CampusAdmissionCycle.admission_cycle_id == effective_cycle_id,
        )
    )

    if current_staff.role == StaffRoleType.CAMPUS_ADMIN:
        accessible_campuses = get_accessible_campuses(current_staff, db)
        accessible_campus_ids = [c.id for c in accessible_campuses]
        query = query.filter(
            or_(
                Application.preferred_campus_id.in_(accessible_campus_ids),
                Application.assigned_to == current_staff.id,
            )
        )

    if preferred_campus_id is not None:
        query = query.filter(Application.preferred_campus_id == preferred_campus_id)
    if program_id is not None:
        query = query.filter(ProgramAdmissionCycle.program_id == program_id)
    if quota is not None:
        query = query.join(Application.quota).filter(ProgramQuota.quota_type == quota)
    if status_filter is not None:
        try:
            status_enum = ApplicationStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.value for s in ApplicationStatus]}",
            )
        query = query.filter(Application.status == status_enum)

    query = query.order_by(Application.submitted_at.desc())
    total = query.count()
    applications = query.offset(skip).limit(limit).all()

    result = []
    for app in applications:
        snapshot = app.snapshot
        program_cycle = app.preferred_program_cycle
        program_name = program_cycle.program.name if program_cycle and program_cycle.program else None
        result.append(
            ApplicationListItem(
                id=app.id,
                application_number=app.application_number,
                status=app.status.value,
                submitted_at=app.submitted_at,
                last_updated_at=app.last_updated_at,
                student=ApplicationListStudentSummary(
                    first_name=snapshot.first_name,
                    last_name=snapshot.last_name,
                    primary_email=snapshot.primary_email,
                    identity_number=snapshot.identity_doc_number,
                ),
                preferred_campus_id=app.preferred_campus_id,
                preferred_campus_name=app.preferred_campus.name if app.preferred_campus else None,
                preferred_program_cycle_id=app.preferred_program_cycle_id,
                program_name=program_name,
                quota_id=app.quota_id,
                quota_name=app.quota.quota_name if app.quota else None,
                assigned_to_id=app.assigned_to,
                assigned_to_name=(
                    f"{app.assigned_staff.first_name} {app.assigned_staff.last_name}".strip()
                    if app.assigned_staff else None
                ),
            )
        )
    return PaginatedApplicationListResponse(items=result, total=total)


@application_router.get(
    "/{application_id}",
    response_model=ApplicationDetailResponse,
    summary="Get application by ID (admin)",
)
def get_application(
    application_id: UUID,
    current_staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    """
    Get full application details by ID: application metadata + applicant info + guardians + academic records.
    Does not include documents (use a separate endpoint for those).
    """
    app = (
        db.query(Application)
        .options(
            joinedload(Application.snapshot).joinedload(ApplicationSnapshot.guardians),
            joinedload(Application.snapshot).joinedload(ApplicationSnapshot.academic_records),
            joinedload(Application.preferred_campus),
            joinedload(Application.preferred_program_cycle).joinedload(ProgramAdmissionCycle.program),
            joinedload(Application.quota),
            joinedload(Application.assigned_staff),
        )
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if not _can_access_application(app, current_staff, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    snap = app.snapshot
    guardians = [
        GuardianDetail(
            id=g.id,
            guardian_relationship=g.guardian_relationship,
            first_name=g.first_name,
            last_name=g.last_name,
            cnic=g.cnic,
            phone_number=g.phone_number,
            email=g.email,
            occupation=g.occupation,
            is_primary=g.is_primary,
            created_at=g.created_at,
        )
        for g in (snap.guardians or [])
    ]
    academic_records = [
        AcademicRecordDetail(
            id=a.id,
            level=a.level,
            education_group=a.education_group,
            institute_name=a.institute_name,
            board_name=a.board_name,
            roll_number=a.roll_number,
            year_of_passing=a.year_of_passing,
            total_marks=a.total_marks,
            obtained_marks=a.obtained_marks,
            grade=a.grade,
            # Verification fields skipped for now (see schema)
            created_at=a.created_at,
        )
        for a in (snap.academic_records or [])
    ]
    program_name = None
    if app.preferred_program_cycle and app.preferred_program_cycle.program:
        program_name = app.preferred_program_cycle.program.name
    return ApplicationDetailResponse(
        id=app.id,
        application_number=app.application_number,
        institute_id=app.institute_id,
        status=app.status,
        submitted_at=app.submitted_at,
        last_updated_at=app.last_updated_at,
        decision_notes=app.decision_notes,
        offer_expires_at=app.offer_expires_at,
        created_at=app.created_at,
        updated_at=app.updated_at,
        preferred_campus_id=app.preferred_campus_id,
        preferred_campus_name=app.preferred_campus.name if app.preferred_campus else None,
        preferred_program_cycle_id=app.preferred_program_cycle_id,
        program_name=program_name,
        quota_id=app.quota_id,
        quota_name=app.quota.quota_name if app.quota else None,
        assigned_to_id=app.assigned_to,
        assigned_to_name=(
            f"{app.assigned_staff.first_name} {app.assigned_staff.last_name}".strip()
            if app.assigned_staff else None
        ),
        workflow_instance_id=app.workflow_instance_id,
        profile_captured_at=snap.snapshot_created_at,
        first_name=snap.first_name,
        last_name=snap.last_name,
        father_name=snap.father_name,
        gender=snap.gender,
        date_of_birth=snap.date_of_birth,
        identity_doc_number=snap.identity_doc_number,
        identity_doc_type=snap.identity_doc_type,
        religion=snap.religion,
        nationality=snap.nationality,
        is_disabled=snap.is_disabled,
        disability_details=snap.disability_details,
        primary_email=snap.primary_email,
        primary_phone=snap.primary_phone,
        alternate_phone=snap.alternate_phone,
        street_address=snap.street_address,
        city=snap.city,
        district=snap.district,
        province=snap.province,
        postal_code=snap.postal_code,
        domicile_province=snap.domicile_province,
        domicile_district=snap.domicile_district,
        guardians=guardians,
        academic_records=academic_records,
    )


@application_router.get(
    "/{application_id}/documents",
    response_model=List[ApplicationDocumentItem],
    summary="List application documents (admin)",
)
def list_application_documents(
    application_id: UUID,
    current_staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    """
    List all documents for an application (submitted with application and requested).
    """
    app = (
        db.query(Application)
        .options(joinedload(Application.documents))
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if not _can_access_application(app, current_staff, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return [ApplicationDocumentItem.model_validate(d) for d in (app.documents or [])]


@application_router.get(
    "/{application_id}/comments",
    response_model=List[ApplicationCommentItem],
    summary="List application comments (admin)",
)
def list_application_comments(
    application_id: UUID,
    current_staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    """
    Fetch all comments for an application (staff and student), merged and sorted by created_at.
    """
    app = (
        db.query(Application)
        .options(
            joinedload(Application.staff_comments).joinedload(ApplicationComment.author),
            joinedload(Application.student_comments).joinedload(StudentComment.author),
        )
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if not _can_access_application(app, current_staff, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    comments: List[ApplicationCommentItem] = []
    for c in app.staff_comments or []:
        name = None
        if c.author:
            name = f"{c.author.first_name or ''} {c.author.last_name or ''}".strip() or None
        comments.append(
            ApplicationCommentItem(
                id=c.id,
                comment_text=c.comment_text,
                created_at=c.created_at,
                author_type="staff",
                is_internal=c.is_internal,
                author_display_name=name,
            )
        )
    for c in app.student_comments or []:
        name = None
        if c.author:
            name = f"{c.author.first_name or ''} {c.author.last_name or ''}".strip() or c.author.email
        comments.append(
            ApplicationCommentItem(
                id=c.id,
                comment_text=c.comment_text,
                created_at=c.created_at,
                author_type="student",
                is_internal=None,
                author_display_name=name,
            )
        )
    comments.sort(key=lambda x: x.created_at)
    return comments


@application_router.post(
    "/{application_id}/comments",
    response_model=ApplicationCommentItem,
    status_code=status.HTTP_201_CREATED,
    summary="Add staff comment (admin)",
)
def create_application_comment(
    application_id: UUID,
    body: StaffCommentCreate,
    current_staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    """
    Allow staff to leave a comment on an application. Use is_internal for internal-only notes.
    """
    app = (
        db.query(Application)
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if not _can_access_application(app, current_staff, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    comment = ApplicationComment(
        application_id=app.id,
        comment_text=body.comment_text.strip(),
        is_internal=body.is_internal,
        created_by=current_staff.id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    name = f"{current_staff.first_name or ''} {current_staff.last_name or ''}".strip() or None
    return ApplicationCommentItem(
        id=comment.id,
        comment_text=comment.comment_text,
        created_at=comment.created_at,
        author_type="staff",
        is_internal=comment.is_internal,
        author_display_name=name,
    )


@application_router.post(
    "/{application_id}/documents",
    response_model=ApplicationDocumentItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create document request (admin)",
)
def create_document_request(
    application_id: UUID,
    body: DocumentRequestCreate,
    current_staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    """
    Request a new document from the student. Creates an application document with requested_by set.
    """
    app = (
        db.query(Application)
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if not _can_access_application(app, current_staff, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    now = datetime.utcnow()
    doc = ApplicationDocument(
        application_id=app.id,
        document_type=body.document_type,
        document_name=body.document_name,
        description=body.description,
        is_required=body.is_required,
        requested_by=current_staff.id,
        requested_at=now,
        verification_status=VerificationStatus.PENDING,
    )
    db.add(doc)
    db.add(
        ApplicationLogHistory(
            application_id=app.id,
            action_type="document_request_created",
            details=f"Document requested: {body.document_name}",
            changed_by=current_staff.user_id,
        )
    )
    db.commit()
    db.refresh(doc)
    return ApplicationDocumentItem.model_validate(doc)


@application_router.patch(
    "/{application_id}/documents/{document_id}",
    response_model=ApplicationDocumentItem,
    summary="Update document verification (admin)",
)
def update_document_verification(
    application_id: UUID,
    document_id: UUID,
    body: DocumentVerificationUpdate,
    current_staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    """
    Update document verification status (and rejection_reason when rejecting).
    """
    doc = (
        db.query(ApplicationDocument)
        .options(joinedload(ApplicationDocument.application))
        .filter(
            ApplicationDocument.application_id == application_id,
            ApplicationDocument.id == document_id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not _can_access_application(doc.application, current_staff, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    now = datetime.utcnow()
    doc.verification_status = body.verification_status
    if body.verification_status == VerificationStatus.REJECTED:
        doc.rejection_reason = body.rejection_reason
    if body.verification_status in (VerificationStatus.APPROVED, VerificationStatus.REJECTED):
        doc.verified_by = current_staff.id
        doc.verified_at = now

    details_msg = f"Document '{doc.document_name}' verification set to {body.verification_status.value}"
    if body.verification_status == VerificationStatus.REJECTED and body.rejection_reason:
        details_msg += f": {body.rejection_reason}"
    db.add(
        ApplicationLogHistory(
            application_id=doc.application_id,
            action_type="document_verification_updated",
            details=details_msg,
            changed_by=current_staff.user_id,
        )
    )
    db.commit()
    db.refresh(doc)
    return ApplicationDocumentItem.model_validate(doc)


@application_router.get(
    "/{application_id}/progress",
    response_model=List[WorkflowStepItem],
    summary="Get application workflow progress (admin)",
)
def get_application_progress(
    application_id: UUID,
    current_staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    """
    Return workflow instance steps (progress) for the application.
    Empty list if the application has no workflow instance.
    """
    app = (
        db.query(Application)
        .options(
            joinedload(Application.workflow_instance).joinedload(
                WorkflowInstance.steps
            ).joinedload(WorkflowInstanceStep.workflow_catalog),
        )
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if not _can_access_application(app, current_staff, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    return _progress_response(app)


def _progress_response(app: Application) -> List[WorkflowStepItem]:
    """Build progress (WorkflowStepItem list) from app.workflow_instance.steps."""
    if not app.workflow_instance or not app.workflow_instance.steps:
        return []
    return [
        WorkflowStepItem(
            id=s.id,
            workflow_instance_id=s.workflow_instance_id,
            subflow_key=s.workflow_catalog.subflow_key,
            subflow_version=s.workflow_catalog.version,
            process_id=s.workflow_catalog.process_id,
            name=s.workflow_catalog.name,
            display_order=s.display_order,
            status=WorkflowStepStatus(s.status),
            started_at=s.started_at,
            completed_at=s.completed_at,
            error_message=s.error_message,
            current_tasks=s.current_tasks or [],
        )
        for s in app.workflow_instance.steps
    ]


@application_router.post(
    "/{application_id}/tasks/complete",
    response_model=List[WorkflowStepItem],
    summary="Complete a workflow user task (admin)",
)
def complete_application_task(
    application_id: UUID,
    body: CompleteTaskRequest,
    current_staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    """
    Complete a waiting user task for this application's workflow.
    Use `task_id` from GET /applications/{id}/progress (step's current_tasks).
    """
    app = (
        db.query(Application)
        .options(
            joinedload(Application.workflow_instance).joinedload(
                WorkflowInstance.steps
            ).joinedload(WorkflowInstanceStep.workflow_catalog),
        )
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if not _can_access_application(app, current_staff, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if not app.workflow_instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application has no workflow instance",
        )
    allowed_task_ids = []
    for s in app.workflow_instance.steps:
        allowed_task_ids.extend(s.current_tasks or [])
    if body.task_id not in allowed_task_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"task_id must be one of the current waiting tasks: {allowed_task_ids}",
        )
    task_found, _, _, _ = complete_user_task_and_persist(
        app.workflow_instance,
        db,
        body.task_id,
        body.data,
        current_staff,
    )
    if not task_found:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task not found or already completed",
        )
    db.commit()
    app = (
        db.query(Application)
        .options(
            joinedload(Application.workflow_instance).joinedload(
                WorkflowInstance.steps
            ).joinedload(WorkflowInstanceStep.workflow_catalog),
        )
        .filter(Application.id == application_id)
        .first()
    )
    return _progress_response(app)
