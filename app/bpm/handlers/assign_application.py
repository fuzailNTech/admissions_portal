from datetime import datetime
from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from SpiffWorkflow.task import Task
from app.database.models.auth import User, StaffProfile, StaffCampus, StaffRoleType
from app.database.models.workflow import (
    WorkflowCatalog,
    WorkflowInstance,
    WorkflowInstanceStep,
    WorkflowStepStatus,
)
from app.database.models.application import (
    Application,
    ApplicationStatus,
    ApplicationLogHistory,
    ApplicationLogActionType,
)
from app.database.models.institute import Institute
from app.bpm.handlers.config import service_task
from app.utils.smtp import send_mail_sync


# Parent (student submission) seeds: application_id, application_number, student_name,
# student_email, program_id, campus_id, quota_id in workflow_data.

ASSIGN_APPLICATION_PROCESS_ID = "operation.assign_application_v1"


@service_task("assign_application_v1.prepare_context")
def handle_prepare_context(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Prepare context for assign-application subworkflow.

    Reads workflow_data (application_id, campus_id, ...), resolves institute
    and sets assignment_mode from institute.application_assignment_mode,
    then builds _assign_application_context for auto_assign/notify/post_context.
    """
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data

    application_id_str = workflow_data.get("application_id")
    if not application_id_str or not str(application_id_str).strip():
        raise ValueError("Missing required field: application_id")

    try:
        application_uuid = UUID(str(application_id_str))
    except (ValueError, TypeError):
        raise ValueError("application_id must be a valid UUID")

    application = db.query(Application).filter(Application.id == application_uuid).first()
    if not application:
        raise ValueError("Application not found")

    institute = db.query(Institute).filter(Institute.id == application.institute_id).first()
    if not institute:
        raise ValueError("Institute not found")

    mode_value = institute.application_assignment_mode.value

    # Context only for subflow-only data; parent already has application_id, campus_id, application_number, etc.
    workflow_data["_assign_application_context"] = {
        "prepared_at": datetime.utcnow().isoformat(),
    }

    workflow_data["assignment_mode"] = mode_value
    workflow.data["assignment_mode"] = mode_value
    task.data["assignment_mode"] = mode_value


@service_task("assign_application_v1.auto_assign")
def handle_auto_assign(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Auto-assign application to a campus admin for the preferred campus. Reads application_id, campus_id from parent."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data
    context = workflow_data.get("_assign_application_context", {})

    application_id_str = workflow_data.get("application_id")
    campus_id_str = workflow_data.get("campus_id")
    if not application_id_str or not str(application_id_str).strip():
        raise ValueError("workflow_data missing application_id")
    if not campus_id_str or not str(campus_id_str).strip():
        raise ValueError("workflow_data missing campus_id")

    try:
        application_uuid = UUID(str(application_id_str))
        campus_uuid = UUID(str(campus_id_str))
    except (ValueError, TypeError):
        raise ValueError("application_id and campus_id must be valid UUIDs")

    application = db.query(Application).filter(Application.id == application_uuid).first()
    if not application:
        raise ValueError("Application not found")

    # Round-robin: subquery of assignment counts per staff
    assignment_count = (
        db.query(Application.assigned_to, func.count(Application.id).label("cnt"))
        .filter(Application.assigned_to.isnot(None))
        .group_by(Application.assigned_to)
        .subquery()
    )

    # 1) Prefer campus admin for this campus (round-robin by current assignment count)
    campus_admin = (
        db.query(StaffProfile)
        .options(joinedload(StaffProfile.user))
        .join(StaffCampus, StaffCampus.staff_profile_id == StaffProfile.id)
        .filter(
            StaffProfile.institute_id == application.institute_id,
            StaffProfile.role == StaffRoleType.CAMPUS_ADMIN,
            StaffProfile.is_active == True,
            StaffCampus.campus_id == campus_uuid,
            StaffCampus.is_active == True,
        )
        .outerjoin(assignment_count, assignment_count.c.assigned_to == StaffProfile.id)
        .order_by(func.coalesce(assignment_count.c.cnt, 0).asc())
        .first()
    )

    if campus_admin:
        eligible = campus_admin
    else:
        # 2) Fallback: institute admins (round-robin)
        eligible = (
            db.query(StaffProfile)
            .options(joinedload(StaffProfile.user))
            .filter(
                StaffProfile.institute_id == application.institute_id,
                StaffProfile.role == StaffRoleType.INSTITUTE_ADMIN,
                StaffProfile.is_active == True,
            )
            .outerjoin(assignment_count, assignment_count.c.assigned_to == StaffProfile.id)
            .order_by(func.coalesce(assignment_count.c.cnt, 0).asc())
            .first()
        )

    # Parent only: assigned_to_id, no_assignee_available. Context only: assignment_method, assigned_to_name, assigned_to_email.
    context["assignment_method"] = "auto"
    if eligible:
        application.assigned_to = eligible.id
        db.add(application)
        db.flush()
        assignee_name = f"{eligible.first_name} {eligible.last_name}".strip() or str(eligible.id)
        assignee_email = eligible.user.email if eligible.user else None
        context["assigned_to_name"] = assignee_name
        context["assigned_to_email"] = assignee_email
        workflow_data["assigned_to_id"] = str(eligible.id)
        workflow_data["no_assignee_available"] = False
    else:
        context["assigned_to_name"] = None
        context["assigned_to_email"] = None
        workflow_data["assigned_to_id"] = None
        workflow_data["no_assignee_available"] = True


def _assignment_notification_body(assignee_name: str, application_number: str) -> str:
    """HTML body for assignee notification email."""
    return f"""
    <p>Dear {assignee_name or 'Staff'},</p>
    <p>A new application has been assigned to you.</p>
    <p><strong>Application number:</strong> {application_number or 'N/A'}</p>
    <p>Please log in to the admissions portal to review and process it.</p>
    <p>Best regards,<br/>Admissions Team</p>
    """


@service_task("assign_application_v1.notify_assignee")
def handle_notify_assignee(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Notify the assigned staff by email. Skips if no assignee. Reads assignee from context, no_assignee/app_number from parent."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data
    context = workflow_data.get("_assign_application_context", {})

    assigned_to_email = context.get("assigned_to_email")
    assigned_to_name = context.get("assigned_to_name") or "Staff"
    no_assignee_available = workflow_data.get("no_assignee_available", True)
    application_number = workflow_data.get("application_number") or "N/A"

    attempted_at = datetime.utcnow().isoformat()
    if assigned_to_email and not no_assignee_available:
        subject = f"Application assigned to you - {application_number}"
        body = _assignment_notification_body(assigned_to_name, application_number)
        try:
            send_mail_sync(
                recipients=assigned_to_email,
                subject=subject,
                body=body.strip(),
            )
            context["assignee_notified"] = True
            context["assignee_notified_at"] = attempted_at
            context["assignee_notified_error"] = None
        except Exception as e:
            context["assignee_notified"] = False
            context["assignee_notified_at"] = attempted_at
            context["assignee_notified_error"] = str(e)
    else:
        context["assignee_notified"] = False
        context["assignee_notified_at"] = attempted_at
        context["assignee_notified_error"] = None


@service_task("assign_application_v1.post_context")
def handle_post_context(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Update step status. Reads assignee_notified/error from context, no_assignee_available from parent."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data
    context = workflow_data.get("_assign_application_context") or {}
    now = datetime.utcnow()

    assignee_notified = context.get("assignee_notified", False)
    no_assignee_available = workflow_data.get("no_assignee_available", True)
    assignee_notified_error = context.get("assignee_notified_error")

    step = (
        db.query(WorkflowInstanceStep)
        .join(WorkflowCatalog, WorkflowInstanceStep.workflow_catalog_id == WorkflowCatalog.id)
        .filter(
            WorkflowInstanceStep.workflow_instance_id == wf_row.id,
            WorkflowCatalog.process_id == ASSIGN_APPLICATION_PROCESS_ID,
        )
        .first()
    )
    if step:
        step.status = WorkflowStepStatus.COMPLETED.value
        step.completed_at = now
        step.current_tasks = []
        if no_assignee_available:
            step.error_message = "No eligible assignee for preferred campus; fallback to institute admin or unassigned."
        elif not assignee_notified and assignee_notified_error:
            step.error_message = f"Assignee notification failed: {assignee_notified_error}"
        else:
            step.error_message = None
        db.add(step)

    application_id_str = workflow_data.get("application_id")
    if application_id_str:
        try:
            application_uuid = UUID(str(application_id_str))
            application = db.query(Application).filter(Application.id == application_uuid).first()
            if application:
                old_status = application.status
                from_status = getattr(old_status, "value", str(old_status))
                application.status = ApplicationStatus.SUBMITTED.value
                assigned_to_email = context.get("assigned_to_email")
                no_assignee = workflow_data.get("no_assignee_available", True)
                if assigned_to_email:
                    assign_details = f"Application assigned to {assigned_to_email}"
                elif not no_assignee:
                    assign_name = context.get("assigned_to_name")
                    assign_details = (
                        f"Application assigned to {assign_name}" if assign_name else "Application assigned"
                    )
                else:
                    assign_details = "Assignment step completed; no eligible assignee"
                meta = {"from_status": from_status, "to_status": ApplicationStatus.SUBMITTED.value}
                if assigned_to_email:
                    meta["assigned_to_email"] = assigned_to_email
                db.add(
                    ApplicationLogHistory(
                        application_id=application.id,
                        action_type=ApplicationLogActionType.APPLICATION_ASSIGNED,
                        details=assign_details,
                        metadata_=meta,
                        changed_by=None,
                    )
                )
                db.add(application)
        except (ValueError, TypeError):
            pass
