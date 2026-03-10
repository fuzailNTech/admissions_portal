from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from SpiffWorkflow.task import Task

from app.database.models.application import Application, ApplicationStatus
from app.database.models.auth import User
from app.database.models.workflow import (
    WorkflowCatalog,
    WorkflowInstance,
    WorkflowInstanceStep,
    WorkflowStepStatus,
)
from app.bpm.handlers.config import service_task
from app.utils.smtp import send_mail_sync


# Parent workflow_data already has application_id, application_number, student_email, student_name, decision, decision_notes.

ADMISSION_DECISION_PROCESS_ID = "operation.admission_decision_v1"


def _get_application_from_workflow(workflow_data: dict, db: Session) -> Application:
    """Load Application from workflow_data application_id."""
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
    return application


def _update_application_decision(
    application: Application,
    status: ApplicationStatus,
    decision_notes: str | None,
    db: Session,
) -> None:
    """Set application status, decision_notes, last_updated_at and commit."""
    application.status = status
    application.decision_notes = decision_notes
    application.last_updated_at = datetime.utcnow()
    db.commit()


def _offer_email_body(student_name: str, application_number: str) -> str:
    """HTML body for admission offer email."""
    return f"""
    <p>Dear {student_name or 'Applicant'},</p>
    <p>We are pleased to inform you that you have been <strong>offered</strong> admission.</p>
    <p><strong>Application number:</strong> {application_number or 'N/A'}</p>
    <p>Please log in to the admissions portal to view details and accept the offer within the specified period.</p>
    <p>Best regards,<br/>Admissions Team</p>
    """


def _rejection_email_body(student_name: str, application_number: str) -> str:
    """HTML body for admission rejection email."""
    return f"""
    <p>Dear {student_name or 'Applicant'},</p>
    <p>Thank you for your application. After careful review, we are unable to offer you admission at this time.</p>
    <p><strong>Application number:</strong> {application_number or 'N/A'}</p>
    <p>We wish you the best in your future endeavours.</p>
    <p>Best regards,<br/>Admissions Team</p>
    """


@service_task("admission_decision_v1.prepare_context")
def handle_prepare_context(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Prepare context for admission-decision subworkflow.

    Reads application_id from parent workflow_data, validates and loads Application.
    Writes only _admission_decision_context with subflow-only data (e.g. prepared_at).
    """
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data

    _get_application_from_workflow(workflow_data, db)

    workflow_data["_admission_decision_context"] = {
        "prepared_at": datetime.utcnow().isoformat(),
    }


@service_task("admission_decision_v1.offered")
def handle_offered(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Update application status to OFFERED, persist decision_notes, and send offer email to student."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data

    application = _get_application_from_workflow(workflow_data, db)
    decision_notes = workflow_data.get("decision_notes")

    _update_application_decision(
        application, ApplicationStatus.OFFERED, decision_notes, db
    )

    recipient = (
        workflow_data.get("student_email")
        or workflow_data.get("applicant_email")
        or workflow_data.get("email")
    )
    if recipient and str(recipient).strip():
        application_number = workflow_data.get("application_number") or "N/A"
        student_name = workflow_data.get("student_name") or "Applicant"
        subject = f"Admission offer - {application_number}"
        body = _offer_email_body(student_name, application_number)
        try:
            send_mail_sync(recipients=str(recipient).strip(), subject=subject, body=body)
        except Exception as e:
            print(f"Failed to send offer email: {e}")


@service_task("admission_decision_v1.rejected")
def handle_rejected(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Update application status to REJECTED, persist decision_notes, and send rejection email to student."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data

    application = _get_application_from_workflow(workflow_data, db)
    decision_notes = workflow_data.get("decision_notes")

    _update_application_decision(
        application, ApplicationStatus.REJECTED, decision_notes, db
    )

    recipient = (
        workflow_data.get("student_email")
        or workflow_data.get("applicant_email")
        or workflow_data.get("email")
    )
    if recipient and str(recipient).strip():
        application_number = workflow_data.get("application_number") or "N/A"
        student_name = workflow_data.get("student_name") or "Applicant"
        subject = f"Admission decision - {application_number}"
        body = _rejection_email_body(student_name, application_number)
        try:
            send_mail_sync(recipients=str(recipient).strip(), subject=subject, body=body)
        except Exception as e:
            print(f"Failed to send rejection email: {e}")


@service_task("admission_decision_v1.on_hold")
def handle_on_hold(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Update application status to ON_HOLD and persist decision_notes. No email."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data

    application = _get_application_from_workflow(workflow_data, db)
    decision_notes = workflow_data.get("decision_notes")

    _update_application_decision(
        application, ApplicationStatus.ON_HOLD, decision_notes, db
    )


@service_task("admission_decision_v1.post_context")
def handle_post_context(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Mark admission-decision step as COMPLETED and clear subflow context. Runs after offered or rejected."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data
    now = datetime.utcnow()

    step = (
        db.query(WorkflowInstanceStep)
        .join(WorkflowCatalog, WorkflowInstanceStep.workflow_catalog_id == WorkflowCatalog.id)
        .filter(
            WorkflowInstanceStep.workflow_instance_id == wf_row.id,
            WorkflowCatalog.process_id == ADMISSION_DECISION_PROCESS_ID,
        )
        .first()
    )
    if step:
        step.status = WorkflowStepStatus.COMPLETED.value
        step.error_message = None
        step.completed_at = now
        step.current_tasks = []
        db.add(step)
    db.commit()

    if "_admission_decision_context" in workflow_data:
        del workflow_data["_admission_decision_context"]
