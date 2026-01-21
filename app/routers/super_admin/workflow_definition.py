from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from uuid import UUID
from datetime import datetime

from app.database.config.db import get_db
from app.database.models.workflow import WorkflowDefinition, WorkflowCatalog
from app.database.models.institute import Institute
from app.database.models.auth import User
from app.schema.super_admin.workflow_definition import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowDefinitionResponse,
    WorkflowDefinitionDetailResponse,
)
from app.utils.auth import get_current_active_user
from app.bpm.compiler.compiler import compile_manifest_to_bpmn

workflow_definition_router = APIRouter(
    prefix="/workflow-definition",
    tags=["Super Admin Workflow Definition Management"],
)


def create_catalog_lookup(db: Session):
    """
    Create a catalog lookup function for the compiler.
    """

    def catalog_lookup(key: str, version: int) -> dict:
        """Look up a subworkflow in the catalog."""
        subworkflow = (
            db.query(WorkflowCatalog)
            .filter(
                WorkflowCatalog.subflow_key == key,
                WorkflowCatalog.version == version,
                WorkflowCatalog.published == True,
            )
            .first()
        )

        if not subworkflow:
            raise ValueError(
                f"Subworkflow '{key}_{version}' not found in catalog or not published"
            )

        return {
            "process_id": subworkflow.process_id,
            "checksum": f"sha256:{subworkflow.id}",  # Placeholder
            "description": subworkflow.description or "",
        }

    return catalog_lookup


@workflow_definition_router.post(
    "/institute/{institute_id}",
    response_model=WorkflowDefinitionDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workflow_definition(
    institute_id: UUID,
    workflow_def: WorkflowDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new workflow definition for an institute.
    The manifest will be compiled to BPMN XML automatically.
    """
    try:
        # Verify institute exists
        institute = db.query(Institute).filter(Institute.id == institute_id).first()
        if not institute:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Institute with id {institute_id} not found",
            )

        # Check if workflow with same process_id and version already exists
        process_id = (
            workflow_def.manifest_json.get(
                "process_id", workflow_def.manifest_json.get("workflow_name", "Parent")
            )
            .replace(" ", "_")
            .replace("-", "_")
        )

        existing = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.institute_id == institute_id,
                WorkflowDefinition.process_id == process_id,
                WorkflowDefinition.version == workflow_def.version,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Workflow definition with process_id '{process_id}' and version {workflow_def.version} already exists for this institute",
            )

        # Compile manifest to BPMN XML
        catalog_lookup = create_catalog_lookup(db)

        try:
            bpmn_xml, subprocess_refs = compile_manifest_to_bpmn(
                workflow_def.manifest_json, catalog_lookup=catalog_lookup
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Manifest compilation error: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error compiling manifest: {str(e)}",
            )

        # Create workflow definition
        db_workflow_def = WorkflowDefinition(
            institute_id=institute_id,
            process_id=process_id,
            workflow_name=workflow_def.workflow_name,
            version=workflow_def.version,
            manifest_json=workflow_def.manifest_json,
            bpmn_xml=bpmn_xml,
            subprocess_refs=subprocess_refs,
            published=workflow_def.published,
            active=workflow_def.active,
            created_by=current_user.id,
        )

        # Set published_at if publishing
        if workflow_def.published:
            db_workflow_def.published_at = datetime.utcnow()

        db.add(db_workflow_def)
        db.commit()
        db.refresh(db_workflow_def)

        return db_workflow_def

    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow definition with this process_id and version already exists",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating workflow definition: {str(e)}",
        )


@workflow_definition_router.get(
    "/institute/{institute_id}", response_model=List[WorkflowDefinitionResponse]
)
def list_workflow_definitions(
    institute_id: UUID,
    skip: int = 0,
    limit: int = 100,
    published: bool = None,
    active: bool = None,
    db: Session = Depends(get_db),
):
    """
    List all workflow definitions for an institute.
    """
    # Verify institute exists
    institute = db.query(Institute).filter(Institute.id == institute_id).first()
    if not institute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institute with id {institute_id} not found",
        )

    query = db.query(WorkflowDefinition).filter(
        WorkflowDefinition.institute_id == institute_id
    )

    # Apply filters
    if published is not None:
        query = query.filter(WorkflowDefinition.published == published)

    if active is not None:
        query = query.filter(WorkflowDefinition.active == active)

    # Order by workflow_name and version
    query = query.order_by(
        WorkflowDefinition.workflow_name, WorkflowDefinition.version.desc()
    )

    # Apply pagination
    workflow_defs = query.offset(skip).limit(limit).all()

    return workflow_defs


@workflow_definition_router.get(
    "/{workflow_definition_id}", response_model=WorkflowDefinitionDetailResponse
)
def get_workflow_definition(
    workflow_definition_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get a specific workflow definition by ID.
    Returns full details including bpmn_xml and manifest_json.
    """
    workflow_def = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.id == workflow_definition_id)
        .first()
    )

    if not workflow_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow definition with id {workflow_definition_id} not found",
        )

    return workflow_def


@workflow_definition_router.patch(
    "/{workflow_definition_id}", response_model=WorkflowDefinitionDetailResponse
)
def update_workflow_definition(
    workflow_definition_id: UUID,
    workflow_def_update: WorkflowDefinitionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update a workflow definition.
    Only provided fields will be updated.
    If manifest_json is updated, BPMN XML will be recompiled.
    """
    db_workflow_def = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.id == workflow_definition_id)
        .first()
    )

    if not db_workflow_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow definition with id {workflow_definition_id} not found",
        )

    # Update only provided fields
    update_data = workflow_def_update.model_dump(exclude_unset=True)

    # If manifest_json is updated, recompile BPMN XML
    if "manifest_json" in update_data:
        catalog_lookup = create_catalog_lookup(db)

        try:
            process_id = (
                update_data["manifest_json"]
                .get(
                    "process_id",
                    update_data["manifest_json"].get("workflow_name", "Parent"),
                )
                .replace(" ", "_")
                .replace("-", "_")
            )

            bpmn_xml, subprocess_refs = compile_manifest_to_bpmn(
                update_data["manifest_json"], catalog_lookup=catalog_lookup
            )
            update_data["bpmn_xml"] = bpmn_xml
            update_data["subprocess_refs"] = subprocess_refs
            update_data["process_id"] = process_id
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Manifest compilation error: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error compiling manifest: {str(e)}",
            )

    # Handle published_at timestamp
    if "published" in update_data:
        if update_data["published"] and not db_workflow_def.published:
            # Publishing for the first time
            update_data["published_at"] = datetime.utcnow()
        elif not update_data["published"]:
            # Unpublishing
            update_data["published_at"] = None

    for field, value in update_data.items():
        setattr(db_workflow_def, field, value)

    try:
        db.commit()
        db.refresh(db_workflow_def)
        return db_workflow_def

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update would violate unique constraint",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating workflow definition: {str(e)}",
        )
