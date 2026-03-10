"""User task handler for assign_application_v1.select_assignee (manual assignment)."""
from typing import Any, Dict
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.database.models.application import Application
from app.database.models.auth import StaffProfile
from app.bpm.user_task_handlers.config import register_user_task_handler

SELECT_ASSIGNEE_TASK_ID = "assign_application_v1.select_assignee"


def _validate_select_assignee_data(
    data: Dict[str, Any], application_id: Any, db: Session
) -> Dict[str, Any]:
    """Validate assigned_to_id is a staff in the same institute as the application."""
    assigned_to_id = data.get("assigned_to_id")
    if not assigned_to_id:
        raise ValueError("assigned_to_id is required for manual assignment")
    try:
        assignee_uuid = UUID(str(assigned_to_id))
    except (ValueError, TypeError):
        raise ValueError("assigned_to_id must be a valid UUID")
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise ValueError("Application not found")
    staff = db.query(StaffProfile).filter(StaffProfile.id == assignee_uuid).first()
    if not staff:
        raise ValueError("Assigned staff not found")
    if staff.institute_id != app.institute_id:
        raise ValueError("Assigned staff must belong to the same institute as the application")
    if not staff.is_active:
        raise ValueError("Assigned staff is not active")
    return {
        "assigned_to_id": str(assignee_uuid),
        "no_assignee_available": False,
        "assignment_method": "manual",
    }


def _enrich_assignee_for_workflow(
    validated: Dict[str, Any], assignee_uuid: UUID, db: Session
) -> Dict[str, Any]:
    """Add assigned_to_name and assigned_to_email for notify_assignee (writes to parent)."""
    staff = (
        db.query(StaffProfile)
        .options(joinedload(StaffProfile.user))
        .filter(StaffProfile.id == assignee_uuid)
        .first()
    )
    if not staff:
        return validated
    name = f"{staff.first_name} {staff.last_name}".strip() or str(staff.id)
    email = staff.user.email if staff.user else None
    validated["assigned_to_name"] = name
    validated["assigned_to_email"] = email
    return validated


@register_user_task_handler(SELECT_ASSIGNEE_TASK_ID)
def handle_select_assignee_complete(
    application_id: Any,
    task_data: Dict[str, Any],
    db: Session,
    staff: StaffProfile,
) -> Dict[str, Any]:
    """
    Validate manual assignee selection and set Application.assigned_to.
    Returns dict to merge into workflow data for notify_assignee/post_context.
    """
    validated = _validate_select_assignee_data(task_data, application_id, db)
    app = db.query(Application).filter(Application.id == application_id).first()
    if app:
        assignee_uuid = UUID(validated["assigned_to_id"])
        app.assigned_to = assignee_uuid
        db.add(app)
        validated = _enrich_assignee_for_workflow(validated, assignee_uuid, db)
    return validated
