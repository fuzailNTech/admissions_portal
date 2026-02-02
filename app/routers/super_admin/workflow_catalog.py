from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.workflow import WorkflowCatalog
from app.database.models.auth import User
from app.schema.super_admin.workflow_catalog import (
    SubworkflowCreate,
    SubworkflowUpdate,
    SubworkflowResponse,
    SubworkflowDetailResponse,
)
from app.utils.auth import get_current_active_user
import json
from app.bpm.engine import load_spec_from_xml

workflow_catalog_router = APIRouter(
    prefix="/subworkflow",
    tags=["Super Admin - Workflow Catalog Management"],
)


@workflow_catalog_router.post(
    "", response_model=SubworkflowDetailResponse, status_code=status.HTTP_201_CREATED
)
def create_subworkflow(
    subworkflow: SubworkflowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new subworkflow in the catalog.
    """
    try:
        # Check if subworkflow with same key and version already exists
        existing = (
            db.query(WorkflowCatalog)
            .filter(
                WorkflowCatalog.subflow_key == subworkflow.subflow_key,
                WorkflowCatalog.version == subworkflow.version,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Subworkflow with key '{subworkflow.subflow_key}' and version {subworkflow.version} already exists",
            )

        db_subworkflow = WorkflowCatalog(
            subflow_key=subworkflow.subflow_key,
            version=subworkflow.version,
            process_id=subworkflow.process_id,
            bpmn_xml=subworkflow.bpmn_xml,
            description=subworkflow.description,
            published=subworkflow.published,
            created_by=current_user.id,
        )

        db.add(db_subworkflow)
        db.commit()
        db.refresh(db_subworkflow)

        return db_subworkflow

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subworkflow with this key and version already exists",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating subworkflow: {str(e)}",
        )


@workflow_catalog_router.get("", response_model=List[SubworkflowResponse])
def list_subworkflows(
    skip: int = 0,
    limit: int = 100,
    published: bool = None,
    subflow_key: str = None,
    db: Session = Depends(get_db),
):
    """
    List all subworkflows in the catalog.
    Returns list without bpmn_xml for performance.
    """
    query = db.query(WorkflowCatalog)

    # Apply filters
    if published is not None:
        query = query.filter(WorkflowCatalog.published == published)

    if subflow_key:
        query = query.filter(WorkflowCatalog.subflow_key == subflow_key)

    # Order by subflow_key and version
    query = query.order_by(WorkflowCatalog.subflow_key, WorkflowCatalog.version)

    # Apply pagination
    subworkflows = query.offset(skip).limit(limit).all()

    return subworkflows


@workflow_catalog_router.get(
    "/{subworkflow_id}", response_model=SubworkflowDetailResponse
)
def get_subworkflow(
    subworkflow_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get a specific subworkflow by ID.
    Returns full details including bpmn_xml.
    """
    subworkflow = (
        db.query(WorkflowCatalog).filter(WorkflowCatalog.id == subworkflow_id).first()
    )

    if not subworkflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subworkflow with id {subworkflow_id} not found",
        )

    return subworkflow


@workflow_catalog_router.patch(
    "/{subworkflow_id}", response_model=SubworkflowDetailResponse
)
def update_subworkflow(
    subworkflow_id: UUID,
    subworkflow_update: SubworkflowUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update a subworkflow.
    Only provided fields will be updated.
    """
    db_subworkflow = (
        db.query(WorkflowCatalog).filter(WorkflowCatalog.id == subworkflow_id).first()
    )

    if not db_subworkflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subworkflow with id {subworkflow_id} not found",
        )

    # Update only provided fields
    update_data = subworkflow_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_subworkflow, field, value)

    try:
        db.commit()
        db.refresh(db_subworkflow)
        return db_subworkflow

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
            detail=f"Error updating subworkflow: {str(e)}",
        )
