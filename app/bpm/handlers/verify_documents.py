from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from SpiffWorkflow.task import Task

from app.database.models.application import Application
from app.database.models.auth import User
from app.database.models.workflow import (
    WorkflowCatalog,
    WorkflowInstance,
    WorkflowInstanceStep,
    WorkflowStepStatus,
)
from app.bpm.handlers.config import service_task
from app.utils.smtp import send_mail_sync


# Parent workflow_data already has application_id, application_number, student_email, student_name, etc.

VERIFY_DOCUMENTS_PROCESS_ID = "operation.verify_documents_v1"


def _verification_succeeded_email_body(student_name: str, application_number: str) -> str:
    """HTML body for document verification succeeded email."""
    return f"""
    <p>Dear {student_name or 'Applicant'},</p>
    <p>Your documents have been verified successfully.</p>
    <p><strong>Application number:</strong> {application_number or 'N/A'}</p>
    <p>You can track your application status using this number.</p>
    <p>Best regards,<br/>Admissions Team</p>
    """


def _verification_failed_email_body(student_name: str, application_number: str) -> str:
    """HTML body for document verification failed email."""
    return f"""
    <p>Dear {student_name or 'Applicant'},</p>
    <p>Unfortunately, your document verification could not be completed successfully.</p>
    <p><strong>Application number:</strong> {application_number or 'N/A'}</p>
    <p>Please log in to the admissions portal to view details and take any required action.</p>
    <p>Best regards,<br/>Admissions Team</p>
    """


@service_task("verify_documents_v1.prepare_context")
def handle_prepare_context(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Prepare context for verify-documents subworkflow.

    Reads application_id from parent workflow_data, validates and loads Application.
    Writes only _verify_documents_context with subflow-only data (e.g. prepared_at).
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

    # Context only for subflow-only data; parent already has application_id, etc.
    workflow_data["_verify_documents_context"] = {
        "prepared_at": datetime.utcnow().isoformat(),
    }


@service_task("verify_documents_v1.succeeded")
def handle_succeeded(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Send email to student that document verification succeeded. Reads student_email from parent."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data
    recipient = (
        workflow_data.get("student_email")
        or workflow_data.get("applicant_email")
        or workflow_data.get("email")
    )
    if not recipient or not str(recipient).strip():
        return
    application_number = workflow_data.get("application_number") or "N/A"
    student_name = workflow_data.get("student_name") or "Applicant"
    subject = f"Document verification successful - {application_number}"
    body = _verification_succeeded_email_body(student_name, application_number)
    try:
        send_mail_sync(recipients=recipient, subject=subject, body=body.strip())
    except Exception:
        pass


@service_task("verify_documents_v1.failed")
def handle_failed(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Send email to student that document verification failed. Reads student_email from parent."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data
    recipient = (
        workflow_data.get("student_email")
        or workflow_data.get("applicant_email")
        or workflow_data.get("email")
    )
    if not recipient or not str(recipient).strip():
        return
    application_number = workflow_data.get("application_number") or "N/A"
    student_name = workflow_data.get("student_name") or "Applicant"
    subject = f"Document verification unsuccessful - {application_number}"
    body = _verification_failed_email_body(student_name, application_number)
    try:
        send_mail_sync(recipients=recipient, subject=subject, body=body.strip())
    except Exception:
        pass


@service_task("verify_documents_v1.post_context")
def handle_post_context(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Update step status: rejected -> FAILED, otherwise COMPLETED. Reads verification_status from parent."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data
    now = datetime.utcnow()
    verification_status = workflow_data.get("verification_status")

    step = (
        db.query(WorkflowInstanceStep)
        .join(WorkflowCatalog, WorkflowInstanceStep.workflow_catalog_id == WorkflowCatalog.id)
        .filter(
            WorkflowInstanceStep.workflow_instance_id == wf_row.id,
            WorkflowCatalog.process_id == VERIFY_DOCUMENTS_PROCESS_ID,
        )
        .first()
    )
    if step:
        if verification_status == "rejected":
            step.status = WorkflowStepStatus.FAILED.value
            step.error_message = "Document verification rejected."
        else:
            step.status = WorkflowStepStatus.COMPLETED.value
            step.error_message = None
        step.completed_at = now
        step.current_tasks = []
        db.add(step)
