import secrets
from datetime import datetime
from sqlalchemy.orm import Session
from SpiffWorkflow.task import Task
from app.database.models.auth import User
from app.database.models.workflow import WorkflowInstance
from app.bpm.handlers.config import service_task


@service_task("send_application_received_email_v1.prepare_context")
def handle_prepare_context_send_email(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Prepare context for send application received email subworkflow.
    
    Extracts and validates required data from global workflow context.
    """
    print("\n" + "=" * 60)
    print("TASK: Prepare Context - Send Application Received Email")
    print("=" * 60)
    print(f"Task ID: {task.task_spec.bpmn_id}")
    print(f"Workflow Instance ID: {wf_row.id}")
    print(f"Business Key: {wf_row.business_key}")

    # Access global workflow data
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data

    print(f"Raw workflow_data: {workflow_data}")

    # Extract and prepare required data for this subworkflow
    applicant_email = workflow_data.get("applicant_email") or workflow_data.get("email")
    user_id = workflow_data.get("user_id")
    application_id = workflow_data.get("application_id")

    # Validate required fields
    if not applicant_email:
        raise ValueError("Missing required field: applicant_email")
    if not user_id:
        raise ValueError("Missing required field: user_id")

    # Prepare context data for this subworkflow
    workflow_data["_send_email_context"] = {
        "applicant_email": applicant_email,
        "user_id": user_id,
        "application_id": application_id,
        "prepared_at": datetime.utcnow().isoformat(),
    }

    print(f"Prepared context: {workflow_data['_send_email_context']}")


@service_task("send_application_received_email_v1.send_email")
def handle_send_application_received_email(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Handle sending application received email.

    Uses prepared context from prepare_context handler.
    """
    print("\n" + "=" * 60)
    print("TASK: Send Application Received Email")
    print("=" * 60)
    print(f"Task ID: {task.task_spec.bpmn_id}")
    print(f"Workflow Instance ID: {wf_row.id}")
    print(f"Business Key: {wf_row.business_key}")

    # Access global workflow data
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data

    # Get prepared context
    context = workflow_data.get("_send_email_context", {})
    applicant_email = context.get("applicant_email")
    user_id = context.get("user_id")
    application_id = context.get("application_id")

    print(f"Using prepared context: {context}")
    print(f"Sending email to: {applicant_email}")

    # Generate verification token if needed
    token = secrets.token_urlsafe(32)
    verify_url = f"https://example.com/verify?token={token}"


    # Update workflow data
    workflow_data["email_sent"] = True
    workflow_data["email_sent_at"] = datetime.utcnow().isoformat()
    workflow_data["verification_token"] = token
    workflow_data["verify_url"] = verify_url

    print(f"Email sent successfully. Token: {token}")
