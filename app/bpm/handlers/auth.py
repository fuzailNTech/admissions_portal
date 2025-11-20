import secrets
from datetime import datetime
from typing import Dict, Callable
from sqlalchemy.orm import Session
from SpiffWorkflow.task import Task
from app.database.models.auth import VerificationToken, User
from app.database.models.workflow import WorkflowInstance


ServiceHandler = Callable[[Task], None]
SERVICE_HANDLERS: Dict[str, ServiceHandler] = {}


def service_task(name: str):
    def _decorator(fn: ServiceHandler):
        SERVICE_HANDLERS[name] = fn
        return fn

    return _decorator


# "Send email" task: generate token, persist, (stub) send mail
@service_task("send_verification_email")
def handle_send_verification_email(
    task: Task, db: Session, wf_row: WorkflowInstance, user: User
):
    # idempotent: reuse existing active token if present
    existing = (
        db.query(VerificationToken)
        .filter(
            VerificationToken.user_id == user.id,
            VerificationToken.workflow_instance_id == wf_row.id,
            VerificationToken.consumed_at.is_(None),
        )
        .order_by(VerificationToken.expires_at.desc())
        .first()
    )

    if existing:
        token_value = existing.token
    else:
        token_value = secrets.token_urlsafe(24)
        vt = VerificationToken(
            user_id=user.id,
            workflow_instance_id=wf_row.id,
            token=token_value,
        )
        db.add(vt)
        db.flush()  # get ids

    # pretend to send email
    print(f"[DEV] Email to {user.email}: verify via /auth/verify?token={token_value}")
    # mark sent_at
    db.query(VerificationToken).filter_by(token=token_value).update(
        {"sent_at": datetime.utcnow()}
    )

    # expose token to process vars if you want (not required)
    task.data["token"] = token_value


# "Create user" task: mark verified (idempotent)
@service_task("verify_user")
def handle_verify_user(task: Task, db: Session, wf_row: WorkflowInstance, user: User):
    print("Workflow data:", task.workflow.data)
    if not task.workflow.data.get("user_verified", False):
        raise Exception("User not verified, cannot complete task.")
    if not user.verified:
        user.verified = True
        db.add(user)
        db.flush()
        print(f"[DEV] User {user.id} marked as verified")
