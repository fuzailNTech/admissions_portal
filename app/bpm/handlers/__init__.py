from app.bpm.handlers.auth import task_send_verification_email, task_verify_user

HANDLERS = {
    "task_send_email": task_send_verification_email,
    "task_verify_user": task_verify_user,
}
