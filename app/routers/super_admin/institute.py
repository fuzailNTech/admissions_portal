from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from typing import List, Optional
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.institute import Institute, InstituteStatus
from app.database.models.auth import User
from app.schema.super_admin.institute import (
    InstituteCreate,
    InstituteUpdate,
    InstituteResponse,
)
from app.utils.auth import require_super_admin

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
    skip: int = 0,
    limit: int = 100,
    status: Optional[InstituteStatus] = None,
    institute_type: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    List all institutes.
    
    Super admin can view all institutes with optional filters:
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


@institute_router.get("/{institute_id}", response_model=InstituteResponse)
def get_institute(
    institute_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get a specific institute by ID.
    """
    institute = db.query(Institute).filter(Institute.id == institute_id).first()

    if not institute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institute with id {institute_id} not found",
        )

    return institute


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
