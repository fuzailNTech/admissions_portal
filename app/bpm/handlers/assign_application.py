from app.bpm.handlers.config import service_task
import secrets
from datetime import datetime
from sqlalchemy.orm import Session
from SpiffWorkflow.task import Task
from app.database.models.auth import User
from app.database.models.workflow import WorkflowInstance


@service_task("assign_application_v1.prepare_context")
def handle_prepare_context_assign_application(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Prepare context for assign application subworkflow.

    Extracts and validates required data from global workflow context.
    """
    print("\n" + "=" * 60)
    print("TASK: Prepare Context - Assign Application")
    print("=" * 60)
    print(f"Task ID: {task.task_spec.bpmn_id}")
    print(f"Workflow Instance ID: {wf_row.id}")
    print(f"Business Key: {wf_row.business_key}")

    # Access global workflow data
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data

    print(f"Raw workflow_data: {workflow_data}")

    # Extract and prepare required data for this subworkflow
    application_data = workflow_data.get("application") or workflow_data.get(
        "application_data"
    )
    user_id = workflow_data.get("user_id")

    # Get assignment mode (default to "auto" if not specified)
    assignment_mode = workflow_data.get("assignment_mode", "manual")

    # Validate required fields
    if not application_data:
        raise ValueError("Missing required field: application_data")

    application_id = application_data.get("id")
    if not application_id:
        raise ValueError("Missing required field: application_id")

    # Prepare context data for this subworkflow
    workflow_data["_assign_application_context"] = {
        "application_id": application_id,
        "application_data": application_data,
        "user_id": user_id,
        "assignment_mode": assignment_mode,
        "prepared_at": datetime.utcnow().isoformat(),
    }

    # Set assignment_mode in workflow data for gateway condition
    # 1. Parent workflow data (for handlers)
    workflow_data["assignment_mode"] = assignment_mode
    # 2. Subworkflow data (for handlers)
    workflow.data["assignment_mode"] = assignment_mode
    # 3. TASK data (for gateway condition evaluation) ← ADD THIS
    task.data["assignment_mode"] = assignment_mode

    print(f"Prepared context: {workflow_data['_assign_application_context']}")
    print(f"Assignment mode: {assignment_mode}")


@service_task("assign_application_v1.auto_assign")
def handle_auto_assign_application(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Handle auto-assigning application to an officer.

    Uses prepared context from prepare_context handler.
    """
    print("\n" + "=" * 60)
    print("TASK: Auto Assign Application")
    print("=" * 60)
    print(f"Task ID: {task.task_spec.bpmn_id}")
    print(f"Workflow Instance ID: {wf_row.id}")
    print(f"Business Key: {wf_row.business_key}")

    # Access global workflow data
    workflow = task.workflow
    print(f"Workflow data for auto_assign: {workflow.data}")
    workflow_data = workflow.top_workflow.data

    # Get prepared context
    context = workflow_data.get("_assign_application_context", {})
    application_id = context.get("application_id")
    application_data = context.get("application_data")

    print(f"Using prepared context: {context}")

    # Auto-assignment logic (stub)
    assigned_officer = "John Doe"  # Replace with actual assignment logic
    assignment_id = secrets.token_urlsafe(16)

    # Update workflow data
    workflow_data["assigned_officer"] = assigned_officer
    workflow_data["assignment_id"] = assignment_id
    workflow_data["assignment_method"] = "auto"

    print(f"Auto-assigned to: {assigned_officer} (ID: {assignment_id})")


@service_task("assign_application_v1.notify_assignee")
def handle_notify_assignee(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User = None
):
    """Handle notifying the assigned officer.

    Uses prepared context and assignment data.
    """
    print("\n" + "=" * 60)
    print("TASK: Notify Assignee")
    print("=" * 60)
    print(f"Task ID: {task.task_spec.bpmn_id}")
    print(f"Workflow Instance ID: {wf_row.id}")
    print(f"Business Key: {wf_row.business_key}")

    # Access global workflow data
    workflow = task.workflow
    workflow_data = workflow.top_workflow.data

    # Get assignment data
    assigned_officer = workflow_data.get("assigned_officer")
    assignment_id = workflow_data.get("assignment_id")
    application_id = workflow_data.get("application_id")

    print(f"Notifying assignee: {assigned_officer}")
    print(f"Assignment ID: {assignment_id}")
    print(f"Application ID: {application_id}")

    # Notification logic (stub)
    workflow_data["assignee_notified"] = True
    workflow_data["assignee_notified_at"] = datetime.utcnow().isoformat()

    print("Assignee notified successfully")
