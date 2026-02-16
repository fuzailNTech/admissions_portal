from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from typing import List
from app.database.config.db import get_db
from app.database.models.institute import Institute, Campus, Program, CampusProgram
from app.database.models.auth import StaffProfile
from app.schema.admin.institute import (
    # Institute
    InstituteResponse,
    # Campus
    CampusCreate,
    CampusUpdate,
    CampusResponse,
    # Program
    ProgramCreate,
    ProgramUpdate,
    ProgramResponse,
    # CampusProgram
    CampusProgramCreate,
    CampusProgramUpdate,
    CampusProgramResponse,
    CampusWithProgramsResponse,
    ProgramInCampusResponse,
)
from app.utils.auth import (
    get_current_staff,
    is_institute_admin,
    get_accessible_campuses,
    can_access_institute,
    can_access_campus,
)

institute_router = APIRouter(prefix="/institute", tags=["Admin - Institute Management"])


# ==================== INSTITUTE ENDPOINTS ====================

@institute_router.get("", response_model=InstituteResponse)
def get_my_institute(
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Get the institute information for the current staff member.
    
    Staff members can only access their own institute information.
    """
    # Get institute from staff's institute_id
    institute = db.query(Institute).filter(
        Institute.id == staff.institute_id
    ).first()
    
    if not institute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institute not found",
        )
    
    return institute


# ==================== PROGRAM ENDPOINTS ====================


@institute_router.get("/programs", response_model=list[ProgramResponse])
def get_programs(
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Get all programs for the institute.
    
    Only institute admins can view all programs.
    Campus admins will have a separate endpoint for campus-specific programs.
    """
    programs = db.query(Program).filter(
        Program.institute_id == staff.institute_id,
        Program.is_active == True
    ).all()
    
    return programs


@institute_router.post(
    "/programs", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED
)
def create_program(
    program: ProgramCreate,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new program for the institute.
    
    Only institute admins can create programs.
    The program will be created for the staff's institute automatically.
    """
    # Override institute_id with staff's institute
    program_data = program.model_dump()
    program_data['institute_id'] = staff.institute_id
    
    try:
        db_program = Program(**program_data)
        db.add(db_program)
        db.commit()
        db.refresh(db_program)
        return db_program
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Program with code '{program.code}' already exists in your institute",
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
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Update a program.
    
    Only institute admins can update programs.
    Can only update programs in their own institute.
    """
    # Get program
    db_program = db.query(Program).filter(Program.id == program_id).first()
    if not db_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )
    
    # Check if program belongs to staff's institute
    if not can_access_institute(db_program.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this program",
        )

    # Update fields
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
            detail="Program code already exists in your institute",
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
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a program.
    
    Only institute admins can delete programs.
    Can only delete programs in their own institute.
    """
    # Get program
    db_program = db.query(Program).filter(Program.id == program_id).first()
    if not db_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )
    
    # Check if program belongs to staff's institute
    if not can_access_institute(db_program.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this program",
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


# ==================== CAMPUS ENDPOINTS ====================


@institute_router.get("/campuses", response_model=list[CampusResponse])
def get_campuses(
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Get campuses accessible by the current staff member.
    
    - Institute Admin: Returns ALL campuses in their institute
    - Campus Admin: Returns ONLY assigned campuses
    """
    campuses = get_accessible_campuses(staff, db)
    return campuses


@institute_router.post(
    "/campuses", response_model=CampusResponse, status_code=status.HTTP_201_CREATED
)
def create_campus(
    campus: CampusCreate,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new campus for the institute.
    
    Only institute admins can create campuses.
    The campus will be created for the staff's institute automatically.
    """
    # Override institute_id with staff's institute
    campus_data = campus.model_dump()
    campus_data['institute_id'] = staff.institute_id
    campus_data['created_by'] = staff.user_id
    
    try:
        db_campus = Campus(**campus_data)
        db.add(db_campus)
        db.commit()
        db.refresh(db_campus)
        return db_campus
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campus with this code already exists: {str(e)}",
        )
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
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Update a campus.
    
    Only institute admins can update campuses.
    Can only update campuses in their own institute.
    """
    # Get campus
    db_campus = db.query(Campus).filter(Campus.id == campus_id).first()
    if not db_campus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus not found",
        )
    
    # Check if campus belongs to staff's institute
    if not can_access_institute(db_campus.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )

    # Update fields
    update_data = campus_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_campus, field, value)

    try:
        db.commit()
        db.refresh(db_campus)
        return db_campus
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Update failed: {str(e)}",
        )
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
    staff: StaffProfile = Depends(is_institute_admin),
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



# ==================== CAMPUS PROGRAM ENDPOINTS (Junction Table) ====================


@institute_router.get(
    "/campus/{campus_id}/campus-programs",
    response_model=CampusWithProgramsResponse
)
def list_campus_programs(
    campus_id: UUID,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Get detailed campus information with all assigned programs.
    
    Staff can only access if they have access to the campus.
    Returns campus info with nested program details.
    """
    # Verify campus exists and check access
    campus = db.query(Campus).filter(Campus.id == campus_id).first()
    if not campus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus not found",
        )
    
    # Check if staff can access the campus
    if not can_access_campus(campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get all campus-programs with program details
    campus_programs = (
        db.query(CampusProgram, Program)
        .join(Program, CampusProgram.program_id == Program.id)
        .filter(CampusProgram.campus_id == campus_id)
        .all()
    )
    
    # Build program list with details
    programs = []
    for cp, program in campus_programs:
        programs.append(
            ProgramInCampusResponse(
                id=program.id,
                name=program.name,
                code=program.code,
                level=program.level,
                category=program.category,
                duration_years=program.duration_years,
                fee=float(program.fee) if program.fee else None,
                shift=program.shift,
                description=program.description,
                is_active=program.is_active,
                campus_program_id=cp.id,
                campus_program_is_active=cp.is_active,
                campus_program_created_at=cp.created_at,
                campus_program_updated_at=cp.updated_at,
                created_at=program.created_at,
                updated_at=program.updated_at,
            )
        )
    
    # Build response with campus info and programs
    return CampusWithProgramsResponse(
        id=campus.id,
        institute_id=campus.institute_id,
        name=campus.name,
        campus_code=campus.campus_code,
        campus_type=campus.campus_type,
        country=campus.country,
        province_state=campus.province_state,
        city=campus.city,
        postal_code=campus.postal_code,
        address_line=campus.address_line,
        campus_email=campus.campus_email,
        campus_phone=campus.campus_phone,
        timezone=campus.timezone,
        is_active=campus.is_active,
        created_at=campus.created_at,
        updated_at=campus.updated_at,
        programs=programs,
    )


@institute_router.post(
    "/campus/{campus_id}/campus-programs",
    response_model=CampusProgramResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_program_to_campus(
    campus_id: UUID,
    campus_program: CampusProgramCreate,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Assign a program to a campus.
    
    Only institute admins can assign programs to campuses.
    Both campus and program must belong to the staff's institute.
    """
    # Verify campus exists
    campus = db.query(Campus).filter(Campus.id == campus_id).first()
    if not campus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus not found",
        )
    
    # Check if campus belongs to staff's institute
    if not can_access_institute(campus.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )

    # Verify program exists
    program = db.query(Program).filter(Program.id == campus_program.program_id).first()
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )
    
    # Check if program belongs to staff's institute
    if not can_access_institute(program.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this program",
        )

    # Create campus-program with campus_id from path
    campus_program_data = campus_program.model_dump()
    campus_program_data['campus_id'] = campus_id
    campus_program_data['created_by'] = staff.user_id

    try:
        db_campus_program = CampusProgram(**campus_program_data)
        db.add(db_campus_program)
        db.commit()
        db.refresh(db_campus_program)
        return db_campus_program
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This program is already assigned to this campus",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error assigning program to campus: {str(e)}",
        )


@institute_router.patch(
    "/campus/{campus_id}/campus-programs/{campus_program_id}",
    response_model=CampusProgramResponse
)
def update_campus_program(
    campus_id: UUID,
    campus_program_id: UUID,
    campus_program_update: CampusProgramUpdate,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Update a campus-program assignment (e.g., activate/deactivate).
    
    Only institute admins can update campus-program assignments.
    Can only update assignments in their own institute.
    """
    # Verify campus exists and check access
    campus = db.query(Campus).filter(Campus.id == campus_id).first()
    if not campus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus not found",
        )
    
    if not can_access_institute(campus.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get campus-program assignment and verify it belongs to this campus
    db_campus_program = db.query(CampusProgram).filter(
        CampusProgram.id == campus_program_id,
        CampusProgram.campus_id == campus_id
    ).first()
    
    if not db_campus_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus-program assignment not found for this campus",
        )

    # Update fields
    update_data = campus_program_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_campus_program, field, value)

    try:
        db.commit()
        db.refresh(db_campus_program)
        return db_campus_program
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating campus-program assignment: {str(e)}",
        )


@institute_router.delete(
    "/campus/{campus_id}/campus-programs/{campus_program_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def remove_program_from_campus(
    campus_id: UUID,
    campus_program_id: UUID,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Remove a program from a campus.
    
    Only institute admins can remove program assignments.
    Can only remove assignments in their own institute.
    """
    # Verify campus exists and check access
    campus = db.query(Campus).filter(Campus.id == campus_id).first()
    if not campus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus not found",
        )
    
    if not can_access_institute(campus.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get campus-program assignment and verify it belongs to this campus
    db_campus_program = db.query(CampusProgram).filter(
        CampusProgram.id == campus_program_id,
        CampusProgram.campus_id == campus_id
    ).first()
    
    if not db_campus_program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus-program assignment not found for this campus",
        )

    try:
        db.delete(db_campus_program)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing program from campus: {str(e)}",
        )
