from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from app.database.config.db import get_db
from app.database.models.institute import Campus, Program
from app.database.models.auth import User
from app.schema.admin.institute import (
    # Campus
    CampusCreate,
    CampusUpdate,
    CampusResponse,
    # Program
    ProgramCreate,
    ProgramUpdate,
    ProgramResponse,
)
from app.utils.auth import get_current_user

institute_router = APIRouter(prefix="/institute", tags=["Admin Institute Management"])


# ==================== CAMPUS ENDPOINTS ====================


@institute_router.post(
    "/campuses", response_model=CampusResponse, status_code=status.HTTP_201_CREATED
)
def create_campus(
    campus: CampusCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new campus for an institute."""
    try:
        db_campus = Campus(**campus.model_dump())
        db.add(db_campus)
        db.commit()
        db.refresh(db_campus)
        return db_campus
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating campus: {str(e)}",
        )


@institute_router.patch("/campuses/{campus_id}", response_model=CampusResponse)
def update_campus(
    campus_id: UUID,
    campus_update: CampusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a campus."""
    db_campus = db.query(Campus).filter(Campus.id == campus_id).first()
    if not db_campus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campus with id {campus_id} not found",
        )

    update_data = campus_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_campus, field, value)

    try:
        db.commit()
        db.refresh(db_campus)
        return db_campus
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating campus: {str(e)}",
        )


@institute_router.delete(
    "/campuses/{campus_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_campus(
    campus_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a campus."""
    db_campus = db.query(Campus).filter(Campus.id == campus_id).first()
    if not db_campus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campus with id {campus_id} not found",
        )

    try:
        db.delete(db_campus)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting campus: {str(e)}",
        )


# ==================== PROGRAM ENDPOINTS ====================


@institute_router.post(
    "/programs", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED
)
def create_program(
    program: ProgramCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new program."""
    try:
        db_program = Program(**program.model_dump())
        db.add(db_program)
        db.commit()
        db.refresh(db_program)
        return db_program
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Program with code '{program.code}' already exists",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating program: {str(e)}",
        )


@institute_router.patch("/programs/{program_id}", response_model=ProgramResponse)
def update_program(
    program_id: UUID,
    program_update: ProgramUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a program."""
    db_program = db.query(Program).filter(Program.id == program_id).first()
    if not db_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program with id {program_id} not found",
        )

    update_data = program_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_program, field, value)

    try:
        db.commit()
        db.refresh(db_program)
        return db_program
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update would violate unique constraint (code may already exist)",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating program: {str(e)}",
        )


@institute_router.delete(
    "/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_program(
    program_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a program."""
    db_program = db.query(Program).filter(Program.id == program_id).first()
    if not db_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program with id {program_id} not found",
        )

    try:
        db.delete(db_program)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting program: {str(e)}",
        )
