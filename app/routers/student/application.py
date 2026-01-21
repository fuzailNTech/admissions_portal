from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Tuple, Optional
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.workflow import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowCatalog,
)
from app.database.models.institute import Institute
from app.database.models.auth import User
from app.schema.student.application import ApplicationCreate, ApplicationResponse
from app.utils.auth import get_current_active_user
from app.bpm.engine import (
    load_spec_from_xml,
    create_workflow_instance,
    run_service_tasks,
    dumps_wf,
)

application_router = APIRouter(
    prefix="/application",
    tags=["Student Application Management"],
)


def build_subprocess_registry(
    subprocess_refs: list, db: Session
) -> Dict[str, Tuple[str, str]]:
    """
    Build subprocess registry for SpiffWorkflow.

    Args:
        subprocess_refs: List of subprocess references from workflow definition
        db: Database session

    Returns:
        Dict mapping calledElement -> (subprocess_xml, subprocess_id)
        e.g., {"communication.send_email_1": ("<xml>...</xml>", "communication.send_email_1")}
    """
    registry = {}

    for ref in subprocess_refs:
        subflow_key = ref.get("subflow_key")
        version = ref.get("version")
        called_element = ref.get("calledElement")

        if not all([subflow_key, version, called_element]):
            continue

        # Look up subworkflow in catalog
        subworkflow = (
            db.query(WorkflowCatalog)
            .filter(
                WorkflowCatalog.subflow_key == subflow_key,
                WorkflowCatalog.version == version,
                WorkflowCatalog.published == True,
            )
            .first()
        )

        if not subworkflow:
            raise ValueError(
                f"Subworkflow '{subflow_key}_{version}' not found in catalog or not published"
            )

        registry[called_element] = (subworkflow.bpmn_xml, subworkflow.process_id)

    return registry


def get_default_initial_data() -> dict:
    """Generate dummy initial data for workflow execution."""
    return {
        "email": "applicant@example.com",
        "user_id": "12345",
        "application": {
            "id": "app-001",
            "name": "John Doe",
            "marks": 85,
            "documents": [
                {"type": "transcript", "status": "uploaded"},
                {"type": "certificate", "status": "uploaded"},
            ],
        },
        "documents": [
            {"type": "transcript", "url": "https://example.com/transcript.pdf"},
            {"type": "certificate", "url": "https://example.com/certificate.pdf"},
        ],
        "policy": {
            "verification": {"limit": 3},
            "fee": {"base": 1000, "currency": "USD"},
        },
    }


@application_router.post(
    "", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED
)
def create_application(
    application: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new application and start workflow instance.
    Uses the active/published workflow definition for the institute.
    """
    try:
        # Verify institute exists
        institute = (
            db.query(Institute).filter(Institute.id == application.institute_id).first()
        )
        if not institute:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Institute with id {application.institute_id} not found",
            )

        # Get active/published workflow definition for the institute
        workflow_def = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.institute_id == application.institute_id,
                WorkflowDefinition.published == True,
                WorkflowDefinition.active == True,
            )
            .order_by(WorkflowDefinition.version.desc())
            .first()
        )

        if not workflow_def:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active/published workflow definition found for institute {application.institute_id}",
            )

        # Build subprocess registry
        subprocess_refs = workflow_def.subprocess_refs or []
        try:
            subprocess_registry = build_subprocess_registry(subprocess_refs, db)
            print(f"Built subprocess registry with {len(subprocess_registry)} entries:")
            for called_element, (xml, process_id) in subprocess_registry.items():
                print(f"  {called_element} -> process_id: {process_id}")
                # Verify the calledElement matches the process_id in the subprocess XML
                if process_id != called_element:
                    print(
                        f"  ⚠️  WARNING: calledElement '{called_element}' != process_id '{process_id}'"
                    )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        # Load BPMN spec with subprocesses
        try:
            spec, subprocess_specs = load_spec_from_xml(
                xml_string=workflow_def.bpmn_xml,
                spec_name=workflow_def.process_id,
                subprocess_registry=(
                    subprocess_registry if subprocess_registry else None
                ),
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error loading BPMN spec: {str(e)}",
            )

        # Prepare initial data (merge dummy data with provided data)
        default_data = get_default_initial_data()
        initial_data = {**default_data, **(application.initial_data or {})}

        # Create workflow instance with subprocess specs
        workflow = create_workflow_instance(
            spec,
            subprocess_specs=subprocess_specs if subprocess_specs else None,
            data=initial_data,
        )

        # Create workflow instance record
        wf_instance = WorkflowInstance(
            institute_id=application.institute_id,
            workflow_definition_id=workflow_def.id,
            business_key=application.business_key,
            definition=workflow_def.process_id,
            state=dumps_wf(workflow),
            status="running",
        )

        db.add(wf_instance)
        db.flush()  # Flush to get the ID

        # Run the workflow
        try:
            should_persist, waiting_task_ids = run_service_tasks(
                wf=workflow,
                db=db,
                wf_row=wf_instance,
                user=current_user,
                auto_persist=False,  # We'll persist manually
            )

            # Update workflow instance with current state
            wf_instance.state = dumps_wf(workflow)
            wf_instance.current_tasks = waiting_task_ids

            if workflow.is_completed():
                wf_instance.status = "completed"
                from datetime import datetime

                wf_instance.completed_at = datetime.utcnow()

            db.commit()
            db.refresh(wf_instance)

        except Exception as e:
            # Mark workflow as failed
            wf_instance.status = "failed"
            wf_instance.error_message = str(e)
            wf_instance.state = dumps_wf(workflow)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error executing workflow: {str(e)}",
            )

        return wf_instance

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating application: {str(e)}",
        )


@application_router.get(
    "/institute/{institute_id}", response_model=list[ApplicationResponse]
)
def list_applications(
    institute_id: UUID,
    skip: int = 0,
    limit: int = 100,
    status: str = None,
    db: Session = Depends(get_db),
):
    """
    List all applications (workflow instances) for an institute.
    """
    # Verify institute exists
    institute = db.query(Institute).filter(Institute.id == institute_id).first()
    if not institute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institute with id {institute_id} not found",
        )

    query = db.query(WorkflowInstance).filter(
        WorkflowInstance.institute_id == institute_id
    )

    # Apply filters
    if status:
        query = query.filter(WorkflowInstance.status == status)

    # Order by created_at descending
    query = query.order_by(WorkflowInstance.created_at.desc())

    # Apply pagination
    applications = query.offset(skip).limit(limit).all()

    return applications


@application_router.get("/{application_id}", response_model=ApplicationResponse)
def get_application(
    application_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get a specific application (workflow instance) by ID.
    """
    application = (
        db.query(WorkflowInstance).filter(WorkflowInstance.id == application_id).first()
    )

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with id {application_id} not found",
        )

    return application
