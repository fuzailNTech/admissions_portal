import json
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from typing import List, Optional
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.institute import Institute, InstituteStatus
from app.database.models.auth import User, StaffProfile, StaffRoleType
from app.database.models.workflow import WorkflowDefinition, WorkflowCatalog
from app.schema.super_admin.institute import (
    InstituteCreate,
    InstituteUpdate,
    InstituteResponse,
    InstituteDetailResponse,
    InstituteAdminResponse,
    AssignInstituteAdminRequest,
    AssignInstituteAdminResponse,
)
from app.schema.super_admin.workflow_definition import (
    WorkflowDefinitionResponse,
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowDefinitionDetailResponse,
)
from app.utils.auth import require_super_admin, get_current_active_user
from app.bpm.compiler.compiler import compile_manifest_to_bpmn
from app.settings import BASE_DIR

DEFAULT_MANIFEST_PATH = os.path.join(BASE_DIR, "bpm", "compiler", "default-manifest.json")

institute_router = APIRouter(
    prefix="/institutes",
    tags=["Super Admin - Institute Management"],
)


@institute_router.post(
    "", response_model=InstituteResponse, status_code=status.HTTP_201_CREATED
)
def create_institute(
    institute: InstituteCreate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new institute.
    
    Requires super admin role.
    Creates a new educational institute with all required information.
    """
    # Check if institute_code already exists
    existing = db.query(Institute).filter(
        Institute.institute_code == institute.institute_code
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Institute with code '{institute.institute_code}' already exists",
        )

    try:
        # Create new institute
        institute_data = institute.model_dump()
        institute_data['created_by'] = current_user.id
        
        db_institute = Institute(**institute_data)

        db.add(db_institute)
        db.commit()
        db.refresh(db_institute)

        return db_institute

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Institute with this code already exists",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating institute: {str(e)}",
        )


@institute_router.get("", response_model=List[InstituteResponse])
def list_institutes(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[InstituteStatus] = None,
    institute_type: Optional[str] = None,
    search: Optional[str] = None,
):
    """
    List all institutes.
    
    Requires super admin. Optional filters:
    - status: Filter by institute status
    - institute_type: Filter by type (government/private/semi_government)
    - search: Search by name or institute_code
    """
    query = db.query(Institute)

    # Apply filters
    if status is not None:
        query = query.filter(Institute.status == status)
    
    if institute_type is not None:
        query = query.filter(Institute.institute_type == institute_type)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Institute.name.ilike(search_term),
                Institute.institute_code.ilike(search_term)
            )
        )

    # Order by name
    query = query.order_by(Institute.name)

    # Apply pagination
    institutes = query.offset(skip).limit(limit).all()

    return institutes


@institute_router.get("/{institute_id}", response_model=InstituteDetailResponse)
def get_institute(
    institute_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Get a specific institute by ID with its workflow definitions (without bpmn_xml). Requires super admin.
    """
    institute = (
        db.query(Institute)
        .options(selectinload(Institute.workflow_definitions))
        .filter(Institute.id == institute_id)
        .first()
    )

    if not institute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institute with id {institute_id} not found",
        )

    institute_admins = (
        db.query(StaffProfile)
        .filter(
            StaffProfile.institute_id == institute_id,
            StaffProfile.role == StaffRoleType.INSTITUTE_ADMIN,
        )
        .all()
    )

    return InstituteDetailResponse(
        **InstituteResponse.model_validate(institute).model_dump(),
        workflow_definitions=[WorkflowDefinitionResponse.model_validate(w) for w in institute.workflow_definitions],
        admins=[InstituteAdminResponse.model_validate(sp) for sp in institute_admins],
    )


@institute_router.patch("/{institute_id}", response_model=InstituteResponse)
def update_institute(
    institute_id: UUID,
    institute_update: InstituteUpdate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Update an institute.
    
    Requires super admin role.
    Only provided fields will be updated.
    """
    db_institute = db.query(Institute).filter(Institute.id == institute_id).first()

    if not db_institute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institute with id {institute_id} not found",
        )

    # Update only provided fields
    update_data = institute_update.model_dump(exclude_unset=True)
    
    # Check if institute_code is being updated and already exists
    if "institute_code" in update_data:
        existing = (
            db.query(Institute)
            .filter(
                Institute.institute_code == update_data["institute_code"],
                Institute.id != institute_id
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Institute with code '{update_data['institute_code']}' already exists",
            )

    for field, value in update_data.items():
        setattr(db_institute, field, value)

    try:
        db.commit()
        db.refresh(db_institute)
        return db_institute

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update would violate unique constraint (institute_code may already exist)",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating institute: {str(e)}",
        )


@institute_router.delete("/{institute_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_institute(
    institute_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Delete an institute.
    Requires super admin role.
    Note: This will cascade delete related workflow definitions and instances.
    """
    db_institute = db.query(Institute).filter(Institute.id == institute_id).first()

    if not db_institute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institute with id {institute_id} not found",
        )

    try:
        db.delete(db_institute)
        db.commit()
        return None

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting institute: {str(e)}",
        )


@institute_router.post(
    "/assign-institute-admin",
    response_model=AssignInstituteAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_institute_admin(
    assignment: AssignInstituteAdminRequest,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """
    Assign a user as institute admin.
    Creates a StaffProfile with INSTITUTE_ADMIN role. Only super admins can perform this action.
    """
    user = db.query(User).filter(User.id == assignment.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign inactive user as admin",
        )
    if not user.first_name or not user.last_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must have first_name and last_name set before assignment. Update the user first.",
        )
    institute = db.query(Institute).filter(Institute.id == assignment.institute_id).first()
    if not institute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institute not found",
        )
    existing_profile = db.query(StaffProfile).filter(
        StaffProfile.user_id == assignment.user_id
    ).first()
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User already has a staff profile at institute: {existing_profile.institute.name}",
        )
    staff_profile = StaffProfile(
        user_id=assignment.user_id,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=None,
        role=StaffRoleType.INSTITUTE_ADMIN,
        institute_id=assignment.institute_id,
        is_active=True,
        assigned_by=current_user.id,
    )
    db.add(staff_profile)
    db.commit()
    db.refresh(staff_profile)
    return AssignInstituteAdminResponse(
        staff_profile_id=staff_profile.id,
        user_id=staff_profile.user_id,
        institute_id=staff_profile.institute_id,
        assigned_at=staff_profile.assigned_at,
    )


# ==================== Workflow definition (nested under institute) ====================


def _create_catalog_lookup(db: Session):
    def catalog_lookup(key: str, version: int) -> dict:
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
            "checksum": f"sha256:{subworkflow.id}",
            "description": subworkflow.description or "",
        }
    return catalog_lookup


def _load_default_manifest() -> dict:
    if not os.path.isfile(DEFAULT_MANIFEST_PATH):
        raise FileNotFoundError(f"Default manifest not found at {DEFAULT_MANIFEST_PATH}")
    with open(DEFAULT_MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _derive_process_id(workflow_name: str) -> str:
    return workflow_name.strip().replace(" ", "_").replace("-", "_") or "workflow"


def _unpublish_other_workflows(
    db: Session,
    institute_id: UUID,
    exclude_workflow_id: UUID | None = None,
) -> None:
    q = db.query(WorkflowDefinition).filter(
        WorkflowDefinition.institute_id == institute_id,
        WorkflowDefinition.published == True,
    )
    if exclude_workflow_id is not None:
        q = q.filter(WorkflowDefinition.id != exclude_workflow_id)
    for w in q.all():
        w.published = False
        w.published_at = None


@institute_router.post(
    "/{institute_id}/workflow-definition",
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
    Uses the default manifest and overrides workflow_name and process_id with the provided workflow name.
    """
    try:
        institute = db.query(Institute).filter(Institute.id == institute_id).first()
        if not institute:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Institute with id {institute_id} not found",
            )
        try:
            manifest_json = _load_default_manifest().copy()
        except FileNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )
        workflow_name = workflow_def.workflow_name.strip()
        process_id = _derive_process_id(workflow_def.workflow_name)
        manifest_json["workflow_name"] = workflow_name
        manifest_json["process_id"] = process_id
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
        catalog_lookup = _create_catalog_lookup(db)
        try:
            bpmn_xml, subprocess_refs = compile_manifest_to_bpmn(
                manifest_json, catalog_lookup=catalog_lookup
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
        if workflow_def.published:
            _unpublish_other_workflows(db, institute_id)
        db_workflow_def = WorkflowDefinition(
            institute_id=institute_id,
            process_id=process_id,
            workflow_name=workflow_name,
            version=workflow_def.version,
            manifest_json=manifest_json,
            bpmn_xml=bpmn_xml,
            subprocess_refs=subprocess_refs,
            published=workflow_def.published,
            active=workflow_def.active,
            created_by=current_user.id,
        )
        if workflow_def.published:
            db_workflow_def.published_at = datetime.utcnow()
        db.add(db_workflow_def)
        db.commit()
        db.refresh(db_workflow_def)
        return db_workflow_def
    except HTTPException:
        raise
    except IntegrityError:
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


@institute_router.get(
    "/{institute_id}/workflow-definition/{workflow_definition_id}",
    response_model=WorkflowDefinitionDetailResponse,
)
def get_workflow_definition(
    institute_id: UUID,
    workflow_definition_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a workflow definition by ID. Must belong to the given institute."""
    workflow_def = (
        db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.id == workflow_definition_id,
            WorkflowDefinition.institute_id == institute_id,
        )
        .first()
    )
    if not workflow_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow definition not found",
        )
    return workflow_def


@institute_router.patch(
    "/{institute_id}/workflow-definition/{workflow_definition_id}",
    response_model=WorkflowDefinitionDetailResponse,
)
def update_workflow_definition(
    institute_id: UUID,
    workflow_definition_id: UUID,
    workflow_def_update: WorkflowDefinitionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a workflow definition. Must belong to the given institute."""
    db_workflow_def = (
        db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.id == workflow_definition_id,
            WorkflowDefinition.institute_id == institute_id,
        )
        .first()
    )
    if not db_workflow_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow definition not found",
        )
    update_data = workflow_def_update.model_dump(exclude_unset=True)
    if "manifest_json" in update_data:
        catalog_lookup = _create_catalog_lookup(db)
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
    if "published" in update_data:
        if update_data["published"] and not db_workflow_def.published:
            _unpublish_other_workflows(db, db_workflow_def.institute_id, exclude_workflow_id=db_workflow_def.id)
            update_data["published_at"] = datetime.utcnow()
        elif not update_data["published"]:
            update_data["published_at"] = None
    for field, value in update_data.items():
        setattr(db_workflow_def, field, value)
    try:
        db.commit()
        db.refresh(db_workflow_def)
        return db_workflow_def
    except IntegrityError:
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
