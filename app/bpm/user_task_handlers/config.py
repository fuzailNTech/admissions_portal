"""
User task handler registry and runner.
"""
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.models.auth import StaffProfile

# task_id -> (application_id, task_data, db, staff) -> validated task_data dict for workflow
UserTaskHandler = Callable[
    [Any, Dict[str, Any], Session, StaffProfile],
    Dict[str, Any],
]

USER_TASK_HANDLERS: Dict[str, UserTaskHandler] = {}


def register_user_task_handler(task_id: str):
    """Decorator to register a user task handler by task_id."""

    def _decorator(fn: UserTaskHandler):
        USER_TASK_HANDLERS[task_id] = fn
        return fn

    return _decorator


def run_user_task_handler(
    task_id: str,
    application_id: Any,
    task_data: Optional[Dict[str, Any]],
    db: Session,
    staff: StaffProfile,
) -> Dict[str, Any]:
    """
    Run the handler for task_id if registered; validate and return task_data for the engine.
    Raises HTTPException if no handler is registered or on validation error.
    """
    data = task_data or {}
    if task_id not in USER_TASK_HANDLERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No handler registered for task_id: {task_id}",
        )
    try:
        return USER_TASK_HANDLERS[task_id](application_id, data, db, staff)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
