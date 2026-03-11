from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session, joinedload
from typing import Dict, List, Tuple, Optional
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.workflow import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowInstanceStep,
    WorkflowCatalog,
    WorkflowStepStatus,
)
from app.database.models.institute import Institute, Program, Campus
from app.database.models.auth import User
from app.database.models.student import (
    StudentProfile,
    StudentGuardian,
    StudentAcademicRecord,
)
from app.database.models.application import (
    Application,
    ApplicationSnapshot,
    ApplicationGuardianSnapshot,
    ApplicationAcademicSnapshot,
    ApplicationDocument,
    ApplicationLogHistory,
    ApplicationLogActionType,
    ApplicationStatus,
    ApplicationComment,
    StudentComment,
    VerificationStatus,
    DocumentType,
)
from app.database.models.admission import (
    ProgramAdmissionCycle,
    CampusAdmissionCycle,
    AdmissionCycle,
    ProgramQuota,
    AdmissionCycleStatus,
)
from app.schema.student.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationSubmitRequest,
    ApplicationSubmitResponse,
    StudentApplicationStatus,
    StudentApplicationListItem,
    StudentApplicationListResponse,
    StudentApplicationDetailResponse,
    ApplicationTrackStep,
    ApplicationTrackResponse,
    StudentGuardianDetail,
    StudentAcademicRecordDetail,
    DocumentRequestItem,
    DocumentRequestListResponse,
    DocumentRequestUploadRequest,
    StudentCommentCreate,
    StudentCommentItem,
    ApplicationCommentItem,
)
from app.utils.auth import get_current_active_user, get_current_student, get_password_hash, generate_strong_password
from app.utils.admission import generate_application_number
from app.utils.smtp import send_mail
from datetime import datetime, timezone
from app.bpm.engine import (
    load_spec_from_xml,
    create_workflow_instance,
    dumps_wf,
)
from app.utils.engine import run_service_tasks_and_persist_steps

application_router = APIRouter(
    prefix="/application",
    tags=["Student - Application Management"],
)


def _student_status(internal_status: ApplicationStatus) -> StudentApplicationStatus:
    """
    Map internal application status to student-facing status.
    Only mapping: on_hold -> under_review. All other statuses pass through as-is.
    """
    if internal_status == ApplicationStatus.ON_HOLD:
        return StudentApplicationStatus.UNDER_REVIEW
    if internal_status == ApplicationStatus.SUBMITTED:
        return StudentApplicationStatus.SUBMITTED
    if internal_status == ApplicationStatus.UNDER_REVIEW:
        return StudentApplicationStatus.UNDER_REVIEW
    if internal_status == ApplicationStatus.DOCUMENTS_PENDING:
        return StudentApplicationStatus.DOCUMENTS_PENDING
    if internal_status == ApplicationStatus.VERIFIED:
        return StudentApplicationStatus.VERIFIED
    if internal_status == ApplicationStatus.OFFERED:
        return StudentApplicationStatus.OFFERED
    if internal_status == ApplicationStatus.REJECTED:
        return StudentApplicationStatus.REJECTED
    if internal_status == ApplicationStatus.ACCEPTED:
        return StudentApplicationStatus.ACCEPTED
    if internal_status == ApplicationStatus.WITHDRAWN:
        return StudentApplicationStatus.WITHDRAWN
    return StudentApplicationStatus.SUBMITTED


def _student_status_from_string(internal_status_str: str) -> StudentApplicationStatus:
    """Map internal status string (e.g. from log metadata) to student-facing status. Delegates to _student_status."""
    if not internal_status_str or not internal_status_str.strip():
        return StudentApplicationStatus.SUBMITTED
    try:
        return _student_status(ApplicationStatus(internal_status_str.strip().lower()))
    except (ValueError, AttributeError):
        return StudentApplicationStatus.SUBMITTED


def _internal_statuses_for_student_status(student_status: StudentApplicationStatus) -> List[ApplicationStatus]:
    """Internal status(es) that map to this student status. Only under_review -> on_hold; rest are 1:1."""
    if student_status == StudentApplicationStatus.UNDER_REVIEW:
        return [ApplicationStatus.ON_HOLD]
    if student_status == StudentApplicationStatus.SUBMITTED:
        return [ApplicationStatus.SUBMITTED]
    if student_status == StudentApplicationStatus.DOCUMENTS_PENDING:
        return [ApplicationStatus.DOCUMENTS_PENDING]
    if student_status == StudentApplicationStatus.VERIFIED:
        return [ApplicationStatus.VERIFIED]
    if student_status == StudentApplicationStatus.OFFERED:
        return [ApplicationStatus.OFFERED]
    if student_status == StudentApplicationStatus.REJECTED:
        return [ApplicationStatus.REJECTED]
    if student_status == StudentApplicationStatus.ACCEPTED:
        return [ApplicationStatus.ACCEPTED]
    if student_status == StudentApplicationStatus.WITHDRAWN:
        return [ApplicationStatus.WITHDRAWN]
    return []


def _build_application_comments(app: Application) -> List[ApplicationCommentItem]:
    """
    Build merged list of staff (non-internal) and student comments for an application, sorted by created_at.
    Expects app to have staff_comments and student_comments loaded with .author.
    """
    out: List[ApplicationCommentItem] = []
    for c in app.staff_comments or []:
        if c.is_internal:
            continue
        name = None
        if c.author:
            name = f"{c.author.first_name or ''} {c.author.last_name or ''}".strip() or None
        out.append(
            ApplicationCommentItem(
                id=c.id,
                comment_text=c.comment_text,
                created_at=c.created_at,
                author_type="staff",
                author_display_name=name,
            )
        )
    for c in app.student_comments or []:
        name = None
        if c.author:
            name = f"{c.author.first_name or ''} {c.author.last_name or ''}".strip() or c.author.email
        out.append(
            ApplicationCommentItem(
                id=c.id,
                comment_text=c.comment_text,
                created_at=c.created_at,
                author_type="student",
                author_display_name=name,
            )
        )
    out.sort(key=lambda x: x.created_at)
    return out


def build_subprocess_registry(
    subprocess_refs: list, db: Session
) -> Dict[str, Tuple[str, str]]:
    """
    Build subprocess registry for SpiffWorkflow.

    Args:
        subprocess_refs: List of subprocess references from workflow definition
        db: Database session

    Returns:
        Dict mapping calledElement -> (subprocess_xml, subprocess_id)
        e.g., {"communication.send_email_1": ("<xml>...</xml>", "communication.send_email_1")}
    """
    registry = {}

    for ref in subprocess_refs:
        subflow_key = ref.get("subflow_key")
        version = ref.get("version")
        called_element = ref.get("calledElement")

        if not all([subflow_key, version, called_element]):
            continue

        # Look up subworkflow in catalog
        subworkflow = (
            db.query(WorkflowCatalog)
            .filter(
                WorkflowCatalog.subflow_key == subflow_key,
                WorkflowCatalog.version == version,
                WorkflowCatalog.published == True,
            )
            .first()
        )

        if not subworkflow:
            raise ValueError(
                f"Subworkflow '{subflow_key}_{version}' not found in catalog or not published"
            )

        registry[called_element] = (subworkflow.bpmn_xml, subworkflow.process_id)

    return registry


def create_workflow_instance_steps(
    db: Session,
    workflow_instance_id: UUID,
    subprocess_refs: list,
) -> None:
    """
    Create WorkflowInstanceStep rows for each subworkflow in this instance.
    Call after creating and flushing the WorkflowInstance so it has an id.
    Links each step to workflow_catalog (single source of truth for subflow key, version, process_id).
    """
    for i, ref in enumerate(subprocess_refs):
        subflow_key = ref.get("subflow_key")
        version = ref.get("version")
        if not all([subflow_key, version is not None]):
            continue
        catalog = (
            db.query(WorkflowCatalog)
            .filter(
                WorkflowCatalog.subflow_key == subflow_key,
                WorkflowCatalog.version == int(version),
            )
            .first()
        )
        if not catalog:
            raise ValueError(
                f"Subworkflow '{subflow_key}_{version}' not found in catalog"
            )
        step = WorkflowInstanceStep(
            workflow_instance_id=workflow_instance_id,
            workflow_catalog_id=catalog.id,
            display_order=i,
            status=WorkflowStepStatus.PENDING.value,
        )
        db.add(step)
    db.flush()



@application_router.get(
    "",
    response_model=StudentApplicationListResponse,
    summary="List my applications",
)
def list_my_applications(
    student: StudentProfile = Depends(get_current_student),
    db: Session = Depends(get_db),
    status: Optional[StudentApplicationStatus] = Query(None, description="Filter by student-facing status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """
    List the current student's applications (overview only).
    Returns application number, status, submitted date, documents (url + status), and target program/campus/institute names.
    Includes total and per-status counts (student-facing status).
    Optionally filter by status (submitted, under_review, documents_pending, verified, offered, rejected, accepted, withdrawn).
    """
    # Per-status counts across all applications (no pagination, unfiltered)
    all_apps_for_counts = (
        db.query(Application.status)
        .filter(Application.student_profile_id == student.id)
        .all()
    )
    submitted = under_review = documents_pending = verified = offered = rejected = accepted = withdrawn = 0
    for (internal_status,) in all_apps_for_counts:
        student_status = _student_status(internal_status)
        if student_status == StudentApplicationStatus.SUBMITTED:
            submitted += 1
        elif student_status == StudentApplicationStatus.UNDER_REVIEW:
            under_review += 1
        elif student_status == StudentApplicationStatus.DOCUMENTS_PENDING:
            documents_pending += 1
        elif student_status == StudentApplicationStatus.VERIFIED:
            verified += 1
        elif student_status == StudentApplicationStatus.OFFERED:
            offered += 1
        elif student_status == StudentApplicationStatus.REJECTED:
            rejected += 1
        elif student_status == StudentApplicationStatus.ACCEPTED:
            accepted += 1
        elif student_status == StudentApplicationStatus.WITHDRAWN:
            withdrawn += 1

    query = (
        db.query(Application)
        .options(
            joinedload(Application.snapshot),
            joinedload(Application.institute),
            joinedload(Application.preferred_campus),
            joinedload(Application.preferred_program_cycle).joinedload(ProgramAdmissionCycle.program),
            joinedload(Application.quota),
            joinedload(Application.documents),
            joinedload(Application.staff_comments).joinedload(ApplicationComment.author),
            joinedload(Application.student_comments).joinedload(StudentComment.author),
        )
        .filter(Application.student_profile_id == student.id)
    )
    if status is not None:
        internal_statuses = _internal_statuses_for_student_status(status)
        query = query.filter(Application.status.in_(internal_statuses))
    query = query.order_by(Application.submitted_at.desc())
    total = query.count()
    applications = query.offset(skip).limit(limit).all()

    def _doc_to_request_item(d) -> DocumentRequestItem:
        return DocumentRequestItem(
            id=d.id,
            document_type=d.document_type.value,
            document_name=d.document_name,
            description=d.description,
            requested_at=d.requested_at,
            verification_status=d.verification_status,
            uploaded_at=d.uploaded_at,
            file_url=d.file_url,
        )

    items = []
    for app in applications:
        program_name = None
        if app.preferred_program_cycle and app.preferred_program_cycle.program:
            program_name = app.preferred_program_cycle.program.name
        all_docs = app.documents or []
        uploaded_documents = [_doc_to_request_item(d) for d in all_docs if d.requested_by is None]
        requested_uploads = [_doc_to_request_item(d) for d in all_docs if d.requested_by is not None and not d.file_url]
        items.append(
            StudentApplicationListItem(
                id=app.id,
                application_number=app.application_number,
                status=_student_status(app.status),
                submitted_at=app.submitted_at,
                institute_name=app.institute.name if app.institute else None,
                program_name=program_name,
                campus_name=app.preferred_campus.name if app.preferred_campus else None,
                quota_name=app.quota.quota_name if app.quota else None,
                uploaded_documents=uploaded_documents,
                requested_uploads=requested_uploads,
                comments=_build_application_comments(app),
            )
        )
    return StudentApplicationListResponse(
        items=items,
        total=total,
        submitted=submitted,
        under_review=under_review,
        documents_pending=documents_pending,
        verified=verified,
        offered=offered,
        rejected=rejected,
        accepted=accepted,
        withdrawn=withdrawn,
    )


def _build_track_response(app: Application, log_entries: list) -> ApplicationTrackResponse:
    """Build ApplicationTrackResponse for one application from its status_change log entries."""
    steps: List[ApplicationTrackStep] = []
    for entry in log_entries:
        meta = entry.metadata_ or {}
        to_status_str = meta.get("to_status")
        student_status = _student_status_from_string(to_status_str) if to_status_str else StudentApplicationStatus.SUBMITTED
        steps.append(
            ApplicationTrackStep(
                status=student_status,
                created_at=entry.created_at,
            )
        )
    return ApplicationTrackResponse(
        application_number=app.application_number,
        current_status=_student_status(app.status),
        steps=steps,
    )


@application_router.get(
    "/track",
    response_model=List[ApplicationTrackResponse],
    summary="Track all my applications",
)
def track_my_applications(
    student: StudentProfile = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Return tracking for all of the current student's applications.
    Each item has application_number, current_status, and chronological steps from status_change log entries.
    No pagination; returns a plain list.
    """
    applications = (
        db.query(Application)
        .filter(Application.student_profile_id == student.id)
        .order_by(Application.submitted_at.desc())
        .all()
    )

    if not applications:
        return []

    app_ids = [app.id for app in applications]
    log_entries_all = (
        db.query(ApplicationLogHistory)
        .filter(
            ApplicationLogHistory.application_id.in_(app_ids),
            ApplicationLogHistory.action_type == ApplicationLogActionType.STATUS_CHANGE,
        )
        .order_by(ApplicationLogHistory.created_at.asc())
        .all()
    )

    log_by_app: Dict[UUID, List] = {app_id: [] for app_id in app_ids}
    for entry in log_entries_all:
        log_by_app[entry.application_id].append(entry)

    return [
        _build_track_response(app, log_by_app.get(app.id, []))
        for app in applications
    ]


@application_router.get(
    "/{application_id}",
    response_model=StudentApplicationDetailResponse,
    summary="Get my application by ID",
)
def get_my_application(
    application_id: UUID,
    student: StudentProfile = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Get full details of one application belonging to the current student.
    Includes snapshot data (applicant, guardians, academic records) and documents.
    No administrative details (assigned staff, decision notes, workflow internals) are included.
    """
    app = (
        db.query(Application)
        .options(
            joinedload(Application.snapshot).joinedload(ApplicationSnapshot.guardians),
            joinedload(Application.snapshot).joinedload(ApplicationSnapshot.academic_records),
            joinedload(Application.institute),
            joinedload(Application.preferred_campus),
            joinedload(Application.preferred_program_cycle).joinedload(ProgramAdmissionCycle.program),
            joinedload(Application.quota),
            joinedload(Application.documents),
            joinedload(Application.staff_comments).joinedload(ApplicationComment.author),
            joinedload(Application.student_comments).joinedload(StudentComment.author),
        )
        .filter(Application.id == application_id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if app.student_profile_id != student.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    snap = app.snapshot
    guardians = [
        StudentGuardianDetail(
            id=g.id,
            guardian_relationship=g.guardian_relationship,
            first_name=g.first_name,
            last_name=g.last_name,
            phone_number=g.phone_number,
            email=g.email,
            occupation=g.occupation,
        )
        for g in (snap.guardians or [])
    ]
    academic_records = [
        StudentAcademicRecordDetail(
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
        )
        for a in (snap.academic_records or [])
    ]
    all_docs = app.documents or []
    uploaded_documents = [
        DocumentRequestItem(
            id=d.id,
            document_type=d.document_type.value,
            document_name=d.document_name,
            description=d.description,
            requested_at=d.requested_at,
            verification_status=d.verification_status,
            uploaded_at=d.uploaded_at,
            file_url=d.file_url,
        )
        for d in all_docs if d.requested_by is None
    ]
    requested_uploads = [
        DocumentRequestItem(
            id=d.id,
            document_type=d.document_type.value,
            document_name=d.document_name,
            description=d.description,
            requested_at=d.requested_at,
            verification_status=d.verification_status,
            uploaded_at=d.uploaded_at,
            file_url=d.file_url,
        )
        for d in all_docs if d.requested_by is not None and not d.file_url
    ]
    program_name = None
    if app.preferred_program_cycle and app.preferred_program_cycle.program:
        program_name = app.preferred_program_cycle.program.name

    return StudentApplicationDetailResponse(
        id=app.id,
        application_number=app.application_number,
        status=_student_status(app.status),
        submitted_at=app.submitted_at,
        offer_expires_at=app.offer_expires_at,
        institute_id=app.institute_id,
        institute_name=app.institute.name if app.institute else None,
        program_name=program_name,
        campus_name=app.preferred_campus.name if app.preferred_campus else None,
        quota_name=app.quota.quota_name if app.quota else None,
        profile_captured_at=snap.snapshot_created_at,
        first_name=snap.first_name,
        last_name=snap.last_name,
        father_name=snap.father_name,
        gender=snap.gender,
        date_of_birth=snap.date_of_birth,
        identity_doc_type=snap.identity_doc_type,
        identity_doc_number=snap.identity_doc_number,
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
        uploaded_documents=uploaded_documents,
        requested_uploads=requested_uploads,
        comments=_build_application_comments(app),
    )


# @application_router.get(
#     "/{application_id}/comments",
#     response_model=List[ApplicationCommentItem],
#     summary="List application comments (student)",
# )
# def list_application_comments_student(
#     application_id: UUID,
#     student: StudentProfile = Depends(get_current_student),
#     db: Session = Depends(get_db),
# ):
#     """
#     Fetch all comments for an application (staff non-internal + student), merged and sorted by created_at.
#     Same pattern as admin; students only see non-internal staff comments.
#     """
#     app = (
#         db.query(Application)
#         .options(
#             joinedload(Application.staff_comments).joinedload(ApplicationComment.author),
#             joinedload(Application.student_comments).joinedload(StudentComment.author),
#         )
#         .filter(Application.id == application_id)
#         .first()
#     )
#     if not app:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
#     if app.student_profile_id != student.id:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

#     return _build_application_comments(app)


def _get_application_for_student(
    application_id: UUID, student: StudentProfile, db: Session
) -> Application:
    """Return application if it exists and belongs to student; else raise 404."""
    app = (
        db.query(Application)
        .filter(Application.id == application_id, Application.student_profile_id == student.id)
        .first()
    )
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


# @application_router.get(
#     "/{application_id}/document-requests",
#     response_model=DocumentRequestListResponse,
#     summary="List pending document requests",
# )
# def list_document_requests(
#     application_id: UUID,
#     student: StudentProfile = Depends(get_current_student),
#     db: Session = Depends(get_db),
# ):
#     """
#     List document requests for this application that are pending (requested by staff, verification_status = pending).
#     Student can resolve these by uploading a document via PATCH .../documents/{document_id}.
#     """
#     _get_application_for_student(application_id, student, db)
#     documents = (
#         db.query(ApplicationDocument)
#         .filter(
#             ApplicationDocument.application_id == application_id,
#             ApplicationDocument.requested_by.isnot(None),
#             ApplicationDocument.verification_status == VerificationStatus.PENDING,
#         )
#         .order_by(ApplicationDocument.requested_at.asc())
#         .all()
#     )
#     items = [
#         DocumentRequestItem(
#             id=d.id,
#             document_type=d.document_type.value,
#             document_name=d.document_name,
#             description=d.description,
#             requested_at=d.requested_at,
#             verification_status=d.verification_status,
#             uploaded_at=d.uploaded_at,
#             file_url=d.file_url,
#         )
#         for d in documents
#     ]
#     return DocumentRequestListResponse(items=items)


@application_router.patch(
    "/{application_id}/documents/{document_id}",
    response_model=DocumentRequestItem,
    summary="Resolve document request by uploading",
)
def upload_document_request(
    application_id: UUID,
    document_id: UUID,
    body: DocumentRequestUploadRequest,
    student: StudentProfile = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Resolve a document request by providing the document URL (upload).
    Only allowed for documents that were requested by staff (requested_by is set).
    For now the client passes the file URL; S3 upload flow can be added later.
    """
    _get_application_for_student(application_id, student, db)
    doc = (
        db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.id == document_id,
            ApplicationDocument.application_id == application_id,
            ApplicationDocument.requested_by.isnot(None),
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document request not found")

    doc.file_url = body.file_url.strip()
    doc.uploaded_at = datetime.now(timezone.utc)
    doc.uploaded_by = student.user_id
    doc.verification_status = VerificationStatus.PENDING
    db.add(doc)
    db.add(
        ApplicationLogHistory(
            application_id=application_id,
            action_type=ApplicationLogActionType.DOCUMENT_UPLOADED,
            details=f"Document '{doc.document_name}' uploaded by student",
            changed_by=student.user_id,
        )
    )
    # If no document request has file_url null, set application status back to submitted
    open_request_count = (
        db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.application_id == application_id,
            ApplicationDocument.requested_by.isnot(None),
            ApplicationDocument.file_url.is_(None),
        )
        .count()
    )
    if open_request_count == 0:
        app = db.query(Application).filter(Application.id == application_id).first()
        if app:
            old_status = app.status
            from_status = getattr(old_status, "value", str(old_status))
            app.status = ApplicationStatus.SUBMITTED
            db.add(
                ApplicationLogHistory(
                    application_id=application_id,
                    action_type=ApplicationLogActionType.STATUS_CHANGE,
                    details="Status changed to submitted (all document requests fulfilled)",
                    metadata_={"from_status": from_status, "to_status": ApplicationStatus.SUBMITTED.value},
                    changed_by=None
                )
            )
            db.add(app)
    db.commit()
    db.refresh(doc)

    return DocumentRequestItem(
        id=doc.id,
        document_type=doc.document_type.value,
        document_name=doc.document_name,
        description=doc.description,
        requested_at=doc.requested_at,
        verification_status=doc.verification_status,
        uploaded_at=doc.uploaded_at,
        file_url=doc.file_url,
    )


@application_router.post(
    "/{application_id}/comments",
    response_model=StudentCommentItem,
    status_code=status.HTTP_201_CREATED,
    summary="Add comment on application (student)",
)
def create_application_comment_student(
    application_id: UUID,
    body: StudentCommentCreate,
    student: StudentProfile = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Add a comment on one of your applications. Only the owning student can comment.
    """
    app = _get_application_for_student(application_id, student, db)
    comment = StudentComment(
        application_id=app.id,
        comment_text=body.comment_text.strip(),
        created_by=student.user_id,
    )
    db.add(comment)
    db.add(
        ApplicationLogHistory(
            application_id=app.id,
            action_type=ApplicationLogActionType.COMMENT_ADDED,
            details="Student comment added",
            changed_by=student.user_id,
        )
    )
    db.commit()
    db.refresh(comment)
    return StudentCommentItem(
        id=comment.id,
        comment_text=comment.comment_text,
        created_at=comment.created_at,
    )


@application_router.post("/submit", response_model=ApplicationSubmitResponse, status_code=status.HTTP_201_CREATED)
def submit_student_application(
    request: ApplicationSubmitRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Submit student application(s) to one or more programs.
    
    This endpoint allows students to apply without prior login. It handles:
    - New student registration (creates user account with generated password)
    - Returning student applications (uses existing profile)
    - Multiple program applications in a single submission
    - Creates immutable snapshots of submitted data for each application
    
    **Flow:**
    1. Validates all program targets (cycles, quotas, seats availability)
    2. Creates or retrieves student profile (based on identity document)
    3. Creates application snapshots (one per program)
    4. Generates unique application numbers
    5. Sends email with credentials and confirmation
    
    **Authentication:**
    - No login required to submit
    - Credentials sent via email for future tracking
    - Students login using identity document number + password
    
    **Identity Document:**
    - Primary identifier for students
    - Format: XXXXX-XXXXXXX-X (CNIC or B-Form)
    - Prevents duplicate registrations
    
    **All-or-Nothing:**
    - All applications succeed together or all fail
    - Ensures data consistency across multiple program applications
    """
    try:
        # Start transaction
        with db.begin_nested():
            
            # ==================== STEP 1: VALIDATE ALL PROGRAM TARGETS ====================
            # Store resolved program cycles for each application
            program_cycles_map = {}  # Key: index, Value: (program_cycle, admission_cycle)
            
            for idx, program_data in enumerate(request.applied_programs):
                
                # Check institute exists
                institute = db.query(Institute).filter(
                    Institute.id == program_data.institute_id
                ).first()
                if not institute:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Institute with id {program_data.institute_id} not found"
                    )
                
                # Check program exists and belongs to institute
                program = db.query(Program).filter(
                    Program.id == program_data.program_id,
                    Program.institute_id == program_data.institute_id
                ).first()
                if not program:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Program not found or does not belong to this institute"
                    )
                
                # Check campus exists and belongs to institute
                campus = db.query(Campus).filter(
                    Campus.id == program_data.preferred_campus_id,
                    Campus.institute_id == program_data.institute_id
                ).first()
                if not campus:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Campus not found or does not belong to this institute"
                    )
                
                # Get active/open admission cycle for the institute
                admission_cycle = db.query(AdmissionCycle).filter(
                    AdmissionCycle.institute_id == program_data.institute_id,
                    AdmissionCycle.status == AdmissionCycleStatus.OPEN,
                    AdmissionCycle.is_published == True
                ).first()
                if not admission_cycle:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No active admission cycle found for this institute"
                    )
                
                # Check if within application date range
                now = datetime.now(admission_cycle.application_start_date.tzinfo)
                if now < admission_cycle.application_start_date:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Application period has not started yet"
                    )
                if now > admission_cycle.application_end_date:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Application period has ended"
                    )
                
                # Get campus admission cycle
                campus_cycle = db.query(CampusAdmissionCycle).filter(
                    CampusAdmissionCycle.campus_id == program_data.preferred_campus_id,
                    CampusAdmissionCycle.admission_cycle_id == admission_cycle.id
                ).first()
                if not campus_cycle:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Campus is not participating in the current admission cycle"
                    )
                
                # Check if campus is open for applications
                if not campus_cycle.is_open:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Campus is not accepting applications. Reason: {campus_cycle.closure_reason or 'Not specified'}"
                    )
                
                # Find program cycle for this program + campus combination
                program_cycle = db.query(ProgramAdmissionCycle).filter(
                    ProgramAdmissionCycle.program_id == program_data.program_id,
                    ProgramAdmissionCycle.campus_admission_cycle_id == campus_cycle.id
                ).first()
                if not program_cycle:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="This program is not offered at the selected campus for the current admission cycle"
                    )
                
                # Check if program cycle is active
                if not program_cycle.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Program is not currently accepting applications"
                    )
                
                # Check quota exists and is valid
                quota = db.query(ProgramQuota).filter(
                    ProgramQuota.id == program_data.quota_id,
                    ProgramQuota.program_cycle_id == program_cycle.id
                ).first()
                if not quota:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Quota not found or does not belong to this program cycle"
                    )
                
                # Store resolved program cycle and admission cycle for later use
                program_cycles_map[idx] = (program_cycle, admission_cycle)
            
            # ==================== STEP 2: HANDLE USER & PROFILE ====================
            
            # Check if student exists by identity document
            existing_profile = db.query(StudentProfile).filter(
                StudentProfile.identity_doc_number == request.student_profile.identity_doc_number
            ).first()
            
            student_password = None
            is_new_student = False
            
            if existing_profile:
                # ========== RETURNING STUDENT ==========
                user = existing_profile.user
                
                # Security check: verify date of birth matches
                if existing_profile.date_of_birth != request.student_profile.date_of_birth:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Identity document already registered with different date of birth. Please contact support."
                    )
                
                # Security check: verify father name matches
                if existing_profile.father_name != request.student_profile.father_name:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Identity document already registered with different father name. Please contact support."
                    )
                
                # Handle email change
                if user.email != request.student_profile.primary_email:
                    # Check if new email is already taken by someone else
                    email_taken = db.query(User).filter(
                        User.email == request.student_profile.primary_email,
                        User.id != user.id
                    ).first()
                    
                    if email_taken:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This email is already registered with another account. Please use a different email."
                        )
                    
                    # Update email
                    user.email = request.student_profile.primary_email
                
            else:
                # ========== NEW STUDENT ==========
                is_new_student = True
                
                # Check if email is already taken
                existing_user = db.query(User).filter(
                    User.email == request.student_profile.primary_email
                ).first()
                
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This email is already registered. Please use a different email."
                    )
                
                # Generate password
                student_password = generate_strong_password()
                
                # Create user (generated password is temporary until user changes it)
                user = User(
                    email=request.student_profile.primary_email,
                    password_hash=get_password_hash(student_password),
                    is_temporary_password=True,
                    verified=False,
                    is_active=True
                )
                db.add(user)
                db.flush()
                
                # Create student profile
                profile = StudentProfile(
                    user_id=user.id,
                    first_name=request.student_profile.first_name,
                    last_name=request.student_profile.last_name,
                    father_name=request.student_profile.father_name,
                    gender=request.student_profile.gender,
                    date_of_birth=request.student_profile.date_of_birth,
                    identity_doc_number=request.student_profile.identity_doc_number,
                    identity_doc_type=request.student_profile.identity_doc_type,
                    religion=request.student_profile.religion,
                    nationality=request.student_profile.nationality,
                    is_disabled=request.student_profile.is_disabled,
                    disability_details=request.student_profile.disability_details,
                    primary_email=request.student_profile.primary_email,
                    primary_phone=request.student_profile.primary_phone,
                    alternate_phone=request.student_profile.alternate_phone,
                    street_address=request.student_profile.street_address,
                    city=request.student_profile.city,
                    district=request.student_profile.district,
                    province=request.student_profile.province,
                    postal_code=request.student_profile.postal_code,
                    domicile_province=request.student_profile.domicile_province,
                    domicile_district=request.student_profile.domicile_district,
                    profile_picture_url=request.student_profile.profile_picture_url,
                    identity_doc_url=request.student_profile.identity_doc_url,
                )
                db.add(profile)
                db.flush()
                
                # Create guardian
                guardian = StudentGuardian(
                    student_profile_id=profile.id,
                    guardian_relationship=request.guardian.guardian_relationship,
                    first_name=request.guardian.first_name,
                    last_name=request.guardian.last_name,
                    cnic=request.guardian.cnic,
                    phone_number=request.guardian.phone_number,
                    email=request.guardian.email,
                    occupation=request.guardian.occupation,
                    is_primary=request.guardian.is_primary,
                )
                db.add(guardian)
                
                # Create academic record
                academic_record = StudentAcademicRecord(
                    student_profile_id=profile.id,
                    level=request.academic_record.level,
                    education_group=request.academic_record.education_group,
                    institute_name=request.academic_record.institute_name,
                    board_name=request.academic_record.board_name,
                    roll_number=request.academic_record.roll_number,
                    year_of_passing=request.academic_record.year_of_passing,
                    total_marks=request.academic_record.total_marks,
                    obtained_marks=request.academic_record.obtained_marks,
                    grade=request.academic_record.grade,
                    result_card_url=request.academic_record.result_card_url,
                )
                db.add(academic_record)
                db.flush()
                
                existing_profile = profile
            
            # ==================== STEP 3: CREATE APPLICATIONS ====================
            
            application_numbers = []
            
            for idx, program_data in enumerate(request.applied_programs):
                # Get resolved program cycle and admission cycle from validation
                program_cycle, admission_cycle = program_cycles_map[idx]
                academic_year = admission_cycle.academic_year
                
                # Generate application number
                application_number = generate_application_number(
                    db=db,
                    institute_id=program_data.institute_id,
                    academic_year=academic_year
                )
                
                # Create application snapshot (from submitted data)
                snapshot = ApplicationSnapshot(
                    snapshot_created_at=datetime.utcnow(),
                    source_profile_id=existing_profile.id,
                    first_name=request.student_profile.first_name,
                    last_name=request.student_profile.last_name,
                    father_name=request.student_profile.father_name,
                    gender=request.student_profile.gender.value,
                    date_of_birth=request.student_profile.date_of_birth,
                    identity_doc_number=request.student_profile.identity_doc_number,
                    identity_doc_type=request.student_profile.identity_doc_type.value,
                    religion=request.student_profile.religion.value if request.student_profile.religion else None,
                    nationality=request.student_profile.nationality,
                    is_disabled=request.student_profile.is_disabled,
                    disability_details=request.student_profile.disability_details,
                    primary_email=request.student_profile.primary_email,
                    primary_phone=request.student_profile.primary_phone,
                    alternate_phone=request.student_profile.alternate_phone,
                    street_address=request.student_profile.street_address,
                    city=request.student_profile.city,
                    district=request.student_profile.district,
                    province=request.student_profile.province.value,
                    postal_code=request.student_profile.postal_code,
                    domicile_province=request.student_profile.domicile_province.value,
                    domicile_district=request.student_profile.domicile_district,
                    profile_picture_url=request.student_profile.profile_picture_url,
                    identity_doc_url=request.student_profile.identity_doc_url,
                )
                db.add(snapshot)
                db.flush()
                
                # Create guardian snapshot
                guardian_snapshot = ApplicationGuardianSnapshot(
                    application_snapshot_id=snapshot.id,
                    source_guardian_id=None,
                    guardian_relationship=request.guardian.guardian_relationship.value,
                    first_name=request.guardian.first_name,
                    last_name=request.guardian.last_name,
                    cnic=request.guardian.cnic,
                    phone_number=request.guardian.phone_number,
                    email=request.guardian.email,
                    occupation=request.guardian.occupation,
                    is_primary=request.guardian.is_primary,
                )
                db.add(guardian_snapshot)
                
                # Create academic snapshot
                academic_snapshot = ApplicationAcademicSnapshot(
                    application_snapshot_id=snapshot.id,
                    source_academic_id=None,
                    level=request.academic_record.level.value,
                    education_group=request.academic_record.education_group.value if request.academic_record.education_group else None,
                    institute_name=request.academic_record.institute_name,
                    board_name=request.academic_record.board_name,
                    roll_number=request.academic_record.roll_number,
                    year_of_passing=request.academic_record.year_of_passing,
                    total_marks=request.academic_record.total_marks,
                    obtained_marks=request.academic_record.obtained_marks,
                    grade=request.academic_record.grade,
                    result_card_url=request.academic_record.result_card_url,
                    is_verified=False,
                    verification_status=VerificationStatus.PENDING,
                )
                db.add(academic_snapshot)
                db.flush()
                
                # Create application
                application = Application(
                    application_number=application_number,
                    student_profile_id=existing_profile.id,
                    user_id=user.id,
                    application_snapshot_id=snapshot.id,
                    institute_id=program_data.institute_id,
                    preferred_campus_id=program_data.preferred_campus_id,
                    preferred_program_cycle_id=program_cycle.id,
                    quota_id=program_data.quota_id,
                    status=ApplicationStatus.SUBMITTED,
                    submitted_at=datetime.utcnow(),
                    workflow_instance_id=None,  # Will be set if workflow exists
                )
                db.add(application)
                db.flush()
                
                # Log application submitted
                db.add(
                    ApplicationLogHistory(
                        application_id=application.id,
                        action_type=ApplicationLogActionType.STATUS_CHANGE,
                        details="Application submitted by student",
                        metadata_={"to_status": ApplicationStatus.SUBMITTED.value},
                        changed_by=user.id,
                    )
                )

                # Create application documents (single source for this application)
                db.add(
                    ApplicationDocument(
                        application_id=application.id,
                        document_type=DocumentType.PROFILE_PICTURE,
                        document_name="Profile picture",
                        file_url=request.student_profile.profile_picture_url,
                    )
                )
                db.add(
                    ApplicationDocument(
                        application_id=application.id,
                        document_type=DocumentType.IDENTITY_DOCUMENT,
                        document_name="Identity document",
                        file_url=request.student_profile.identity_doc_url,
                    )
                )
                db.add(
                    ApplicationDocument(
                        application_id=application.id,
                        document_type=DocumentType.ACADEMIC_RESULT_CARD,
                        document_name=f"Result card ({request.academic_record.level.value})",
                        file_url=request.academic_record.result_card_url,
                    )
                )

                # ==================== WORKFLOW INTEGRATION ====================
                # Check if there's an active workflow for this institute
                workflow_def = db.query(WorkflowDefinition).filter(
                    WorkflowDefinition.institute_id == program_data.institute_id,
                    WorkflowDefinition.published == True,
                    WorkflowDefinition.active == True,
                ).order_by(WorkflowDefinition.version.desc()).first()
                
                if workflow_def:
                    try:
                        # Build subprocess registry
                        subprocess_refs = workflow_def.subprocess_refs or []
                        subprocess_registry = {}
                        if subprocess_refs:
                            subprocess_registry = build_subprocess_registry(subprocess_refs, db)
                        
                        # Load BPMN spec
                        spec, subprocess_specs = load_spec_from_xml(
                            xml_string=workflow_def.bpmn_xml,
                            spec_name=workflow_def.process_id,
                            subprocess_registry=subprocess_registry if subprocess_registry else None,
                        )
                        
                        # Prepare workflow data with application details
                        workflow_data = {
                            "application_id": str(application.id),
                            "application_number": application_number,
                            "student_name": f"{request.student_profile.first_name} {request.student_profile.last_name}",
                            "student_email": request.student_profile.primary_email,
                            "program_id": str(program_data.program_id),
                            "campus_id": str(program_data.preferred_campus_id),
                            "quota_id": str(program_data.quota_id),
                        }
                        
                        # Create workflow instance
                        workflow = create_workflow_instance(
                            spec,
                            subprocess_specs=subprocess_specs if subprocess_specs else None,
                            data=workflow_data,
                        )
                        
                        # Create workflow instance record
                        wf_instance = WorkflowInstance(
                            institute_id=program_data.institute_id,
                            workflow_definition_id=workflow_def.id,
                            business_key=application_number,
                            definition=workflow_def.process_id,
                            state=dumps_wf(workflow),
                            status="running",
                        )
                        db.add(wf_instance)
                        db.flush()

                        # Create step rows for progress tracking (one per subworkflow)
                        create_workflow_instance_steps(db, wf_instance.id, subprocess_refs)

                        # Link workflow to application
                        application.workflow_instance_id = wf_instance.id

                        # Run service tasks until we hit a user task or completion; persist state and step current_tasks
                        run_service_tasks_and_persist_steps(
                            wf=workflow,
                            db=db,
                            wf_row=wf_instance,
                            user=user,
                            auto_persist=False,
                        )

                    except Exception as wf_error:
                        # Log workflow error but don't fail the application
                        print(f"Warning: Workflow creation failed for application {application_number}: {str(wf_error)}")
                        # Application is still created, just without workflow
                
                application_numbers.append(application_number)
            
            # Commit transaction
            db.commit()
            
            # ==================== STEP 4: SEND NOTIFICATIONS ====================
            # Student credentials email (new students only). Application received email is handled by workflow.
            if is_new_student and student_password:
                print(f"Sending email to {request.student_profile.primary_email} with password {student_password}")
                recipient = request.student_profile.primary_email
                identity_doc = request.student_profile.identity_doc_number
                body_html = (
                    "<p>Welcome to our platform.</p>"
                    "<p>Your account has been created. Use the credentials below to log in:</p>"
                    f"<p><strong>Login (Identity document number):</strong> {identity_doc}</p>"
                    f"<p><strong>Password:</strong> {student_password}</p>"
                    "<p>Please change your password after your first login.</p>"
                )
                background_tasks.add_task(
                    send_mail,
                    recipient,
                    "Welcome – Your login credentials",
                    body_html,
                )
            
            # ==================== STEP 5: RETURN RESPONSE ====================
            return ApplicationSubmitResponse(
                message=f"Application(s) submitted successfully. Check your email for application details and login credentials."
            )
    
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting application: {str(e)}"
        )
