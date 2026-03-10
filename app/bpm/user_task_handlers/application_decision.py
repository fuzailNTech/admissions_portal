"""User task handlers for admission_decision_v1 (decide_admission_status, resume_review)."""
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.database.models.auth import StaffProfile
from app.bpm.user_task_handlers.config import register_user_task_handler

DECIDE_ADMISSION_STATUS_TASK_ID = "admission_decision_v1.decide_admission_status"
RESUME_REVIEW_TASK_ID = "admission_decision_v1.resume_review"

VALID_DECISIONS = ("offered", "rejected", "on_hold")


def _validate_decide_admission_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize task_data for decide admission status."""
    decision = data.get("decision")
    if decision is None:
        raise ValueError("decision is required")
    decision = str(decision).strip().lower()
    if decision not in VALID_DECISIONS:
        raise ValueError(
            f"decision must be one of: {', '.join(VALID_DECISIONS)}"
        )
    decision_notes = data.get("decision_notes")
    if decision_notes is not None and not isinstance(decision_notes, str):
        decision_notes = str(decision_notes)
    return {
        "decision": decision,
        "decision_notes": (decision_notes or "").strip() or None,
    }


@register_user_task_handler(DECIDE_ADMISSION_STATUS_TASK_ID)
def handle_decide_admission_status(
    application_id: Any,
    task_data: Dict[str, Any],
    db: Session,
    staff: StaffProfile,
) -> Dict[str, Any]:
    """
    Validate decide-admission payload and return data for workflow.
    DB update (status, decision_notes) is done in service tasks (offered/rejected/on_hold).
    """
    return _validate_decide_admission_data(task_data)


@register_user_task_handler(RESUME_REVIEW_TASK_ID)
def handle_resume_review(
    application_id: Any,
    task_data: Dict[str, Any],
    db: Session,
    staff: StaffProfile,
) -> Dict[str, Any]:
    """
    Complete the resume-review user task (after on_hold). No required payload; flow returns to decide_admission_status.
    """
    return {}
