from fastapi import APIRouter, Depends, HTTPException
from app.database.config.db import get_db
from app.schema.auth import RegisterUser
from sqlalchemy.orm import Session
from app.database.models.workflow import User, WorkflowInstance
from app.database.models.auth import VerificationToken
from app.bpm import engine
import os
from app.settings import BPMN_DIR
import httpx
import json
from urllib.parse import quote

auth_router = APIRouter(tags=["auth"])

BPMN_PATH = os.path.join(BPMN_DIR, "user_registration.bpmn")
ARENA_BASE = os.getenv("ARENA_BASE", "http://host.docker.internal:8000/v1.0")
USER_REG_PROCESS_MODEL_IDENTIFIER = "admissions:user-registration"

ARENA_BEARER = """eyJhbGciOiJSUzI1NiIsImtpZCI6InNwaWZmd29ya2Zsb3dfYmFja2VuZF9vcGVuX2lkIiwidHlwIjoiSldUIn0.eyJpc3MiOiJodHRwOi8vbG9jYWxob3N0OjgwMDAvb3BlbmlkIiwiYXVkIjpbInNwaWZmd29ya2Zsb3ctYmFja2VuZCIsIm15X29wZW5faWRfc2VjcmV0X2tleSJdLCJpYXQiOjE3NTY3NjI4MjEsImV4cCI6MTc1NjkzNTYyMSwic3ViIjoiYWRtaW4iLCJlbWFpbCI6ImFkbWluQGV4YW1wbGUuY29tIiwicHJlZmVycmVkX3VzZXJuYW1lIjoiQWRtaW4ifQ.QRT4dnI6oqsyevLP_JHm8OhWf2lHllX6U3ARldlz7CXDD0oGO1QEv18G1rlhQAIMyk-soaw4m38BnjaHtyTrJ0xZJGCA-s6pdESITPVmaPzule_CV1g-X6pvuyUSluAouBPIy2N9eNswpb-LzP3KtKLiTCKWVgDzqKHHfn6rL6LqzXheBp4xjNkqmOpTeq4saGe2MIw6dpmdc-JIKUK80lPK5K0EbUBsiFUV_UOSDcJNcRZqbuSJio0QqhkB4eal4k0oypSZWogFJbM-7ykzGWW7NWvyq2sCeA5JviHVxAoJHsgKRlJkejsb4s0HDlJ4M9uFm2HUA3b7ADodJp0YAw"""


@auth_router.post("/register", response_model=dict)
async def register(body: RegisterUser, db: Session = Depends(get_db)):
    try:
        # upsert/find user
        user = db.query(User).filter_by(email=body.email).first()
        if user:
            raise HTTPException(409, "User already registered.")
        if not user:
            user = User(email=body.email, password_hash=body.password, verified=False)
            db.add(user)
            db.flush()

        payload = {
            "email": user.email,
            "verify_url": "http://localhost:3000/verify?token=abc123",
            "user_id": str(user.id),
        }
        print(f"Starting Arena process instance with payload: {json.dumps(payload)}")

        async with httpx.AsyncClient(timeout=15) as c:
            # NOTE: check Arena OpenAPI (/v1.0/ui) for the exact path in your build
            headers = {"Authorization": f"Bearer {ARENA_BEARER}"}
            r = await c.post(
                f"{ARENA_BASE}/process-instances/{USER_REG_PROCESS_MODEL_IDENTIFIER}",
                json=payload,
                headers=headers,
            )
            try:
                r.raise_for_status()
                instance_id = r.json().get("id")
                print(f"Started Arena process instance {instance_id}")
                # Run instance
                res = await c.post(
                    f"{ARENA_BASE}/process-instances/{USER_REG_PROCESS_MODEL_IDENTIFIER}/{instance_id}/run",
                    headers=headers,
                    json=payload,
                )
                print(f"Run response: {res.status_code} {res.text}")
                res.raise_for_status()
            except httpx.HTTPStatusError as e:
                # This shows the exact Arena error (e.g., which ${...} failed)
                detail = e.response.text
                print(f"Arena error: {detail}")
                raise HTTPException(e.response.status_code, f"Arena 400: {detail}")
            return r.json()

        # # load workflow spec
        # spec = engine.load_spec(path=BPMN_PATH)

        # # create new workflow instance row
        # wf = engine.create_workflow_instance(
        #     spec=spec, data={"email": user.email, "user_id": str(user.id)}
        # )
        # wf_row = WorkflowInstance(
        #     definition="user_registration",
        #     state=engine.dumps_wf(wf),
        #     business_key=user.email,
        # )
        # db.add(wf_row)
        # db.flush()  # get ids

        # # advance engine until wait (Send Email runs here)
        # wf = engine.loads_wf(wf_row.state)
        # engine.run_until_waiting(wf=wf, db=db, wf_row=wf_row, user=user)
        db.commit()

        return {
            "message": "Verification email sent (dev stub).",
        }
    except HTTPException as he:
        db.rollback()
        raise he


@auth_router.get("/verify")
def verify(token: str, db: Session = Depends(get_db)):
    try:
        vt = db.query(VerificationToken).filter_by(token=token).first()
        if not vt:
            raise HTTPException(400, "Invalid token.")
        if vt.consumed_at is not None:
            raise HTTPException(409, "Token already used.")
        from datetime import datetime

        # if vt.expires_at <= datetime.utcnow():
        #     raise HTTPException(410, "Token expired.")

        # load workflow + user
        wf_row = (
            db.query(WorkflowInstance).filter_by(id=vt.workflow_instance_id).first()
        )
        if not wf_row:
            raise HTTPException(404, "Workflow instance not found.")
        user = db.query(User).filter_by(id=vt.user_id).first()
        if not user:
            raise HTTPException(404, "User not found.")

        wf = engine.loads_wf(wf_row.state)
        if wf.is_completed():
            raise HTTPException(409, "Workflow already completed.")

        engine.correlate_message(
            wf=wf, name="EmailVerified", data={"user_verified": True}
        )

        # now run Create User and persist
        engine.run_until_waiting(wf=wf, db=db, wf_row=wf_row, user=user)
        # mark token used
        vt.consumed_at = datetime.utcnow()
        db.add(vt)
        db.commit()

        return {
            "message": "Email verified. Account activated.",
            "user_id": str(user.id),
        }
    except HTTPException as he:
        db.rollback()
        raise he


@auth_router.post("/notifications/verify_email")
async def notifications_email(body: dict):
    """This is called by the Connector Proxy.
    Body has: to, subject, template, vars (dict)"""
    to = body.get("to")
    verify_url = body.get("verify_url", "")
    body = body.get("body", "")
    print(f"Sending email to {to} with verify_url {verify_url} and body {body}")
    # TODO: send via your email provider; for now just pretend OK
    return {"ok": True, "to": to, "verify_url": verify_url, "body": body}
