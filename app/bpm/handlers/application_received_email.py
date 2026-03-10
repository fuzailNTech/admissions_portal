from datetime import datetime
from sqlalchemy.orm import Session
from SpiffWorkflow.task import Task
from app.database.models.auth import User
from app.database.models.workflow import (
    WorkflowCatalog,
    WorkflowInstance,
    WorkflowInstanceStep,
    WorkflowStepStatus,
)
from app.bpm.handlers.config import service_task
from app.utils.smtp import send_mail_sync

# BPMN process ID of this subflow (for step lookup)
APPLICATION_RECEIVED_EMAIL_PROCESS_ID = "communication.send_application_received_email_v1"


# Parent (student submission) seeds: application_id, application_number, student_name,
# student_email, program_id, campus_id, quota_id in workflow_data.


@service_task("send_application_received_email_v1.prepare_context")
def handle_prepare_context(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Prepare context for application-received email subworkflow.

    Reads and validates workflow data seeded by the parent (student submission),
    then builds a single _send_email_context for the send_email task.
    """
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data

    # Recipient is required; prefer parent-seeded key, fallback for older/custom data
    recipient_email = (
        workflow_data.get("student_email")
        or workflow_data.get("applicant_email")
        or workflow_data.get("email")
    )
    if not recipient_email or not str(recipient_email).strip():
        raise ValueError("Missing required field: student_email (or applicant_email/email)")

    application_id = workflow_data.get("application_id")
    application_number = workflow_data.get("application_number")
    student_name = workflow_data.get("student_name")
    program_id = workflow_data.get("program_id")
    campus_id = workflow_data.get("campus_id")
    quota_id = workflow_data.get("quota_id")

    workflow_data["_send_email_context"] = {
        "recipient_email": str(recipient_email).strip(),
        "application_id": application_id,
        "application_number": application_number or "",
        "student_name": student_name or "",
        "program_id": program_id,
        "campus_id": campus_id,
        "quota_id": quota_id,
        "prepared_at": datetime.utcnow().isoformat(),
    }


def _application_received_email_body(student_name: str, application_number: str) -> str:
    """HTML body for application received email."""
    return f"""
    <p>Dear {student_name or 'Applicant'},</p>
    <p>We have received your application.</p>
    <p><strong>Application number:</strong> {application_number or 'N/A'}</p>
    <p>You can use this number to track your application status.</p>
    <p>Best regards,<br/>Admissions Team</p>
    """


@service_task("send_application_received_email_v1.send_email")
def handle_send_application_received_email(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Send application-received email and set email_sent flag in workflow data."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data
    context = workflow_data.get("_send_email_context", {})
    recipient_email = context.get("recipient_email") or context.get("applicant_email")
    application_number = context.get("application_number") or ""
    student_name = context.get("student_name") or "Applicant"

    if not recipient_email:
        raise ValueError("_send_email_context missing recipient_email")

    subject = f"Application Received - {application_number}"
    body = _application_received_email_body(student_name, application_number)
    attempted_at = datetime.utcnow().isoformat()

    try:
        send_mail_sync(
            recipients=recipient_email,
            subject=subject,
            body=body.strip(),
        )
        context["email_sent"] = True
        context["email_sent_at"] = attempted_at
        context["email_sent_error"] = None
    except Exception as e:
        context["email_sent"] = False
        context["email_sent_at"] = attempted_at
        context["email_sent_error"] = str(e)
        # Complete the task so workflow continues; parent can read context and retry or alert


@service_task("send_application_received_email_v1.post_context")
def handle_post_context(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Update step status from send result and remove _send_email_context from workflow data."""
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data
    context = workflow_data.get("_send_email_context") or {}

    email_sent = context.get("email_sent", True)
    error_message = context.get("email_sent_error")
    now = datetime.utcnow()
    print("Application Received Email Post Context")
    print(f"email_sent: {email_sent}, error_message: {error_message}")
    print(f"wf_row id: {wf_row.id}")
    print(f"application_received_email_process_id: {APPLICATION_RECEIVED_EMAIL_PROCESS_ID}")
    step = (
        db.query(WorkflowInstanceStep)
        .join(WorkflowCatalog, WorkflowInstanceStep.workflow_catalog_id == WorkflowCatalog.id)
        .filter(
            WorkflowInstanceStep.workflow_instance_id == wf_row.id,
            WorkflowCatalog.process_id == APPLICATION_RECEIVED_EMAIL_PROCESS_ID,
        )
        .first()
    )
    print(f"step: {step}")
    if step:
        step.status = (
            WorkflowStepStatus.COMPLETED.value
            if email_sent
            else WorkflowStepStatus.FAILED.value
        )
        step.completed_at = now
        step.error_message = None if email_sent else (error_message or "Email send failed")
        step.current_tasks = []
        db.add(step)

    if "_send_email_context" in workflow_data:
        del workflow_data["_send_email_context"]
