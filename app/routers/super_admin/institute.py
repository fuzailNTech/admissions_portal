from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.institute import Institute
from app.database.models.auth import User
from app.schema.super_admin.institute import (
    InstituteCreate,
    InstituteUpdate,
    InstituteResponse,
)
from app.utils.auth import get_current_active_user
import re

institute_router = APIRouter(
    prefix="/institute",
    tags=["Super Admin Institute Management"],
)


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from a name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug


@institute_router.post(
    "", response_model=InstituteResponse, status_code=status.HTTP_201_CREATED
)
def create_institute(
    institute: InstituteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new institute.
    Requires super admin role.
    """
    try:
        # Generate slug if not provided
        slug = institute.slug
        if not slug:
            slug = generate_slug(institute.name)

        # Check if slug already exists
        existing = db.query(Institute).filter(Institute.slug == slug).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Institute with slug '{slug}' already exists",
            )

        # Create new institute
        db_institute = Institute(
            name=institute.name,
            slug=slug,
            active=institute.active,
        )

        db.add(db_institute)
        db.commit()
        db.refresh(db_institute)

        return db_institute

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Institute with this slug already exists",
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating institute: {str(e)}",
        )


@institute_router.get("/list", response_model=List[InstituteResponse])
def list_institutes(
    skip: int = 0,
    limit: int = 100,
    active: bool = None,
    db: Session = Depends(get_db),
):
    """
    List all institutes.
    """
    query = db.query(Institute)

    # Apply filters
    if active is not None:
        query = query.filter(Institute.active == active)

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
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

    # Handle slug generation if name is updated but slug is not
    if "name" in update_data and "slug" not in update_data:
        new_slug = generate_slug(update_data["name"])
        # Check if new slug conflicts with existing
        existing = (
            db.query(Institute)
            .filter(Institute.slug == new_slug, Institute.id != institute_id)
            .first()
        )
        if not existing:
            update_data["slug"] = new_slug

    for field, value in update_data.items():
        setattr(db_institute, field, value)

    try:
        db.commit()
        db.refresh(db_institute)
        return db_institute

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update would violate unique constraint (slug may already exist)",
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
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
