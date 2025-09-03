import secrets
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.models.auth import VerificationToken
from app.database.models.workflow import WorkflowInstance, User
from SpiffWorkflow.task import Task


# "Send email" task: generate token, persist, (stub) send mail
def task_send_verification_email(
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
def task_verify_user(task: Task, db: Session, wf_row: WorkflowInstance, user: User):
    print("Workflow data:", task.workflow.data)
    if not task.workflow.data.get("user_verified", False):
        raise Exception("User not verified, cannot complete task.")
    if not user.verified:
        user.verified = True
        db.add(user)
        db.flush()
        print(f"[DEV] User {user.id} marked as verified")
