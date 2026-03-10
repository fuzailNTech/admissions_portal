"""User task handler for verify_documents_v1.verify_documents."""
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.database.models.application import (
    ApplicationDocument,
    VerificationStatus,
)
from app.database.models.auth import StaffProfile
from app.bpm.user_task_handlers.config import register_user_task_handler

VERIFY_DOCUMENTS_TASK_ID = "verify_documents_v1.verify_documents"


def _validate_verify_documents_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize task_data for verify documents completion."""
    verification_status = data.get("verification_status")
    if verification_status not in ("approved", "rejected"):
        raise ValueError(
            "verification_status must be 'approved' or 'rejected'"
        )
    verification_notes = data.get("verification_notes")
    if verification_notes is not None and not isinstance(verification_notes, str):
        verification_notes = str(verification_notes)
    return {
        "verification_status": verification_status,
        "verification_notes": verification_notes or None,
    }


def _ensure_no_documents_pending(application_id: Any, db: Session) -> None:
    """Raise if any ApplicationDocument for this application is still pending verification."""
    pending_count = (
        db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.application_id == application_id,
            ApplicationDocument.verification_status == VerificationStatus.PENDING.value,
        )
        .count()
    )
    if pending_count > 0:
        raise ValueError(
            "All documents must be verified (approved or rejected) before completing this task. "
            f"{pending_count} document(s) still pending."
        )


@register_user_task_handler(VERIFY_DOCUMENTS_TASK_ID)
def handle_verify_documents_complete(
    application_id: Any,
    task_data: Dict[str, Any],
    db: Session,
    staff: StaffProfile,
) -> Dict[str, Any]:
    """
    Validate verify-documents completion payload and ensure all documents are already verified.
    Does not change ApplicationDocument status; staff must verify each document via document API first.
    Returns dict to merge into workflow data (verification_status, verification_notes).
    """
    validated = _validate_verify_documents_data(task_data)
    _ensure_no_documents_pending(application_id, db)
    return validated
