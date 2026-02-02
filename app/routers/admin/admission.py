from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.admission import (
    AdmissionCycle,
    CampusAdmissionCycle,
    ProgramAdmissionCycle,
    ProgramQuota,
    CustomFormField,
    ProgramFormField,
)
from app.database.models.auth import StaffProfile
from app.database.models.institute import Campus
from app.database.models.admission import AdmissionCycleStatus, QuotaStatus
from app.schema.admin.admission import (
    # AdmissionCycle
    AdmissionCycleCreate,
    AdmissionCycleUpdate,
    AdmissionCycleResponse,
    # CampusAdmissionCycle
    CampusAdmissionCycleCreate,
    CampusAdmissionCycleUpdate,
    CampusAdmissionCycleResponse,
    CampusAdmissionCycleDetailResponse,
    # ProgramAdmissionCycle
    ProgramAdmissionCycleCreate,
    ProgramAdmissionCycleUpdate,
    ProgramAdmissionCycleResponse,
    ProgramAdmissionCycleDetailResponse,
    ProgramAdmissionCycleWithQuotasResponse,
    # ProgramQuota
    ProgramQuotaCreate,
    ProgramQuotaUpdate,
    ProgramQuotaResponse,
    # CustomFormField
    CustomFormFieldCreate,
    CustomFormFieldUpdate,
    CustomFormFieldResponse,
    # ProgramFormField
    ProgramFormFieldCreate,
    ProgramFormFieldUpdate,
    ProgramFormFieldResponse,
    ProgramFormFieldDetailResponse,
)
from app.utils.auth import is_institute_admin, can_access_institute, get_current_staff, can_access_campus
from typing import Optional, List

admission_router = APIRouter(
    prefix="/admission",
    tags=["Admin - Admission Management"],
)


# ==================== CUSTOM FORM FIELD ENDPOINTS ====================


@admission_router.get("/form-fields", response_model=List[CustomFormFieldResponse])
def list_custom_form_fields(
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    List all custom form fields for the institute.
    
    Only institute admins can access.
    Returns all form fields created for the institute.
    """
    form_fields = db.query(CustomFormField).filter(
        CustomFormField.institute_id == staff.institute_id
    ).order_by(CustomFormField.created_at.desc()).all()
    
    return form_fields


@admission_router.post(
    "/form-fields",
    response_model=CustomFormFieldResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_custom_form_field(
    form_field: CustomFormFieldCreate,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Create a custom form field for the institute.
    
    Only institute admins can create form fields.
    Institute ID is automatically set from staff's profile.
    """
    # Create form field with institute_id from staff profile
    form_field_data = form_field.model_dump()
    form_field_data['institute_id'] = staff.institute_id
    form_field_data['created_by'] = staff.user_id
    
    try:
        db_form_field = CustomFormField(**form_field_data)
        db.add(db_form_field)
        db.commit()
        db.refresh(db_form_field)
        return db_form_field
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Form field with name '{form_field.field_name}' already exists for this institute",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating custom form field: {str(e)}",
        )


@admission_router.patch(
    "/form-fields/{form_field_id}", response_model=CustomFormFieldResponse
)
def update_custom_form_field(
    form_field_id: UUID,
    form_field_update: CustomFormFieldUpdate,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Update a custom form field.
    
    Only institute admins can update.
    Can only update fields in their own institute.
    """
    # Get form field and verify access
    db_form_field = db.query(CustomFormField).filter(
        CustomFormField.id == form_field_id
    ).first()
    
    if not db_form_field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom form field not found",
        )
    
    # Check if form field belongs to staff's institute
    if not can_access_institute(db_form_field.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this form field",
        )

    # Update fields
    update_data = form_field_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_form_field, field, value)

    try:
        db.commit()
        db.refresh(db_form_field)
        return db_form_field
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Update would violate unique constraint (field_name may already exist)",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating custom form field: {str(e)}",
        )


@admission_router.delete(
    "/form-fields/{form_field_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_custom_form_field(
    form_field_id: UUID,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a custom form field.
    
    Only institute admins can delete.
    Can only delete fields in their own institute.
    This will also cascade delete all program assignments.
    """
    # Get form field and verify access
    db_form_field = db.query(CustomFormField).filter(
        CustomFormField.id == form_field_id
    ).first()
    
    if not db_form_field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom form field not found",
        )
    
    # Check if form field belongs to staff's institute
    if not can_access_institute(db_form_field.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this form field",
        )

    try:
        db.delete(db_form_field)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting custom form field: {str(e)}",
        )



# ==================== PROGRAM FORM FIELD ENDPOINTS ====================


@admission_router.get(
    "/program/{program_id}/form-fields",
    response_model=List[ProgramFormFieldDetailResponse]
)
def list_program_form_fields(
    program_id: UUID,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    List all custom form fields assigned to a program with detailed field info.
    
    Staff can access if the program belongs to their institute.
    Returns form fields with full configuration details ordered by display_order.
    """
    # Get program and verify access
    from app.database.models.institute import Program
    program = db.query(Program).filter(Program.id == program_id).first()
    
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
    
    # Get all program form fields with form field details
    program_form_fields = (
        db.query(ProgramFormField)
        .join(CustomFormField, ProgramFormField.form_field_id == CustomFormField.id)
        .filter(ProgramFormField.program_id == program_id)
        .order_by(ProgramFormField.display_order, ProgramFormField.created_at)
        .all()
    )
    
    # Build detailed response
    result = []
    for pff in program_form_fields:
        result.append(
            ProgramFormFieldDetailResponse(
                id=pff.id,
                program_id=pff.program_id,
                is_required=pff.is_required,
                display_order=pff.display_order,
                created_at=pff.created_at,
                updated_at=pff.updated_at,
                form_field=pff.form_field,  # SQLAlchemy relationship
            )
        )
    
    return result


@admission_router.post(
    "/program/{program_id}/form-fields",
    response_model=ProgramFormFieldResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_form_field_to_program(
    program_id: UUID,
    program_form_field: ProgramFormFieldCreate,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Assign a custom form field to a program.
    
    Only institute admins can assign form fields.
    Both program and form field must belong to the same institute.
    """
    # Get program and verify access
    from app.database.models.institute import Program
    program = db.query(Program).filter(Program.id == program_id).first()
    
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )
    
    if not can_access_institute(program.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this program",
        )
    
    # Verify form field exists and belongs to same institute
    form_field = db.query(CustomFormField).filter(
        CustomFormField.id == program_form_field.form_field_id
    ).first()
    
    if not form_field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form field not found",
        )
    
    if not can_access_institute(form_field.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this form field",
        )
    
    # Create program form field
    program_form_field_data = program_form_field.model_dump()
    program_form_field_data['program_id'] = program_id
    
    try:
        db_program_form_field = ProgramFormField(**program_form_field_data)
        db.add(db_program_form_field)
        db.commit()
        db.refresh(db_program_form_field)
        return db_program_form_field
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This form field is already assigned to this program",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error assigning form field to program: {str(e)}",
        )


@admission_router.patch(
    "/program/{program_id}/form-fields/{program_form_field_id}",
    response_model=ProgramFormFieldResponse,
)
def update_program_form_field(
    program_id: UUID,
    program_form_field_id: UUID,
    program_form_field_update: ProgramFormFieldUpdate,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Update program form field settings (e.g., mark as required, change order).
    
    Only institute admins can update.
    Can only update fields in their own institute.
    """
    # Get program and verify access
    from app.database.models.institute import Program
    program = db.query(Program).filter(Program.id == program_id).first()
    
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )
    
    if not can_access_institute(program.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this program",
        )
    
    # Get program form field and verify it belongs to this program
    db_program_form_field = db.query(ProgramFormField).filter(
        ProgramFormField.id == program_form_field_id,
        ProgramFormField.program_id == program_id
    ).first()

    if not db_program_form_field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form field assignment not found for this program",
        )

    # Update fields
    update_data = program_form_field_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_program_form_field, field, value)

    try:
        db.commit()
        db.refresh(db_program_form_field)
        return db_program_form_field
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating program form field: {str(e)}",
        )


@admission_router.delete(
    "/program/{program_id}/form-fields/{program_form_field_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_form_field_from_program(
    program_id: UUID,
    program_form_field_id: UUID,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Remove a form field from a program.
    
    Only institute admins can remove.
    Can only remove fields from their own institute's programs.
    """
    # Get program and verify access
    from app.database.models.institute import Program
    program = db.query(Program).filter(Program.id == program_id).first()
    
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )
    
    if not can_access_institute(program.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this program",
        )
    
    # Get program form field and verify it belongs to this program
    db_program_form_field = db.query(ProgramFormField).filter(
        ProgramFormField.id == program_form_field_id,
        ProgramFormField.program_id == program_id
    ).first()

    if not db_program_form_field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Form field assignment not found for this program",
        )

    try:
        db.delete(db_program_form_field)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing form field from program: {str(e)}",
        )




# ==================== ADMISSION CYCLE ENDPOINTS ====================


@admission_router.get("/cycles", response_model=List[AdmissionCycleResponse])
def list_admission_cycles(
    status_filter: Optional[AdmissionCycleStatus] = None,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    List all admission cycles for the institute.
    
    Only institute admins can access.
    Optional status filter to filter by AdmissionCycleStatus.
    """
    # Build query for staff's institute
    query = db.query(AdmissionCycle).filter(
        AdmissionCycle.institute_id == staff.institute_id
    )
    
    # Apply status filter if provided
    if status_filter:
        query = query.filter(AdmissionCycle.status == status_filter)
    
    # Order by most recent first
    cycles = query.order_by(AdmissionCycle.created_at.desc()).all()
    
    return cycles


@admission_router.post(
    "/cycles",
    response_model=AdmissionCycleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admission_cycle(
    cycle: AdmissionCycleCreate,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new admission cycle for the institute.
    
    Only institute admins can create admission cycles.
    Institute ID is automatically set from staff's profile.
    """
    # Create cycle with institute_id from staff profile
    cycle_data = cycle.model_dump()
    cycle_data['institute_id'] = staff.institute_id
    cycle_data['created_by'] = staff.user_id
    
    try:
        db_cycle = AdmissionCycle(**cycle_data)
        db.add(db_cycle)
        db.commit()
        db.refresh(db_cycle)
        return db_cycle
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Admission cycle already exists or constraint violation: {str(e)}",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating admission cycle: {str(e)}",
        )


@admission_router.patch("/cycles/{cycle_id}", response_model=AdmissionCycleResponse)
def update_admission_cycle(
    cycle_id: UUID,
    cycle_update: AdmissionCycleUpdate,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Update an admission cycle.
    
    Only institute admins can update cycles.
    Can only update cycles in their own institute.
    """
    # Get cycle and verify access
    db_cycle = db.query(AdmissionCycle).filter(
        AdmissionCycle.id == cycle_id
    ).first()
    
    if not db_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admission cycle not found",
        )
    
    # Check if cycle belongs to staff's institute
    if not can_access_institute(db_cycle.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this admission cycle",
        )

    # Update fields
    update_data = cycle_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_cycle, field, value)

    try:
        db.commit()
        db.refresh(db_cycle)
        return db_cycle
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating admission cycle: {str(e)}",
        )


@admission_router.delete("/cycles/{cycle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admission_cycle(
    cycle_id: UUID,
    staff: StaffProfile = Depends(is_institute_admin),
    db: Session = Depends(get_db),
):
    """
    Delete an admission cycle.
    
    Only institute admins can delete cycles.
    Can only delete cycles in their own institute.
    """
    # Get cycle and verify access
    db_cycle = db.query(AdmissionCycle).filter(
        AdmissionCycle.id == cycle_id
    ).first()
    
    if not db_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admission cycle not found",
        )
    
    # Check if cycle belongs to staff's institute
    if not can_access_institute(db_cycle.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this admission cycle",
        )

    try:
        db.delete(db_cycle)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting admission cycle: {str(e)}",
        )


# ==================== CAMPUS ADMISSION CYCLE ENDPOINTS (Junction Table) ====================


@admission_router.get(
    "/campus/{campus_id}/cycles",
    response_model=List[CampusAdmissionCycleDetailResponse]
)
def list_campus_admission_cycles(
    campus_id: UUID,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    List all admission cycles assigned to a specific campus with detailed cycle info.
    
    Staff can access if they have access to the campus.
    Returns campus-specific settings with nested admission cycle details.
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
    
    # Get all campus admission cycles with admission cycle details
    campus_cycles = (
        db.query(CampusAdmissionCycle)
        .join(AdmissionCycle, CampusAdmissionCycle.admission_cycle_id == AdmissionCycle.id)
        .filter(CampusAdmissionCycle.campus_id == campus_id)
        .order_by(CampusAdmissionCycle.created_at.desc())
        .all()
    )
    
    # Build detailed response
    result = []
    for campus_cycle in campus_cycles:
        result.append(
            CampusAdmissionCycleDetailResponse(
                id=campus_cycle.id,
                campus_id=campus_cycle.campus_id,
                is_open=campus_cycle.is_open,
                closure_reason=campus_cycle.closure_reason,
                custom_metadata=campus_cycle.custom_metadata,
                created_at=campus_cycle.created_at,
                updated_at=campus_cycle.updated_at,
                created_by=campus_cycle.created_by,
                admission_cycle=campus_cycle.admission_cycle,  # SQLAlchemy relationship
            )
        )
    
    return result


@admission_router.post(
    "/campus/{campus_id}/cycles",
    response_model=CampusAdmissionCycleResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_cycle_to_campus(
    campus_id: UUID,
    campus_cycle: CampusAdmissionCycleCreate,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Assign an admission cycle to a campus.
    
    Both institute admins and campus admins (for their assigned campus) can assign cycles.
    Admission cycle must belong to the same institute.
    """
    # Verify campus exists
    campus = db.query(Campus).filter(Campus.id == campus_id).first()
    if not campus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus not found",
        )
    
    # Check if staff can access the campus (works for both institute admin and campus admin)
    if not can_access_campus(campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Verify admission cycle exists and belongs to staff's institute
    admission_cycle = db.query(AdmissionCycle).filter(
        AdmissionCycle.id == campus_cycle.admission_cycle_id
    ).first()
    if not admission_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admission cycle not found",
        )
    
    if not can_access_institute(admission_cycle.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this admission cycle",
        )
    
    # Create campus admission cycle
    campus_cycle_data = campus_cycle.model_dump()
    campus_cycle_data['campus_id'] = campus_id
    campus_cycle_data['created_by'] = staff.user_id
    
    try:
        db_campus_cycle = CampusAdmissionCycle(**campus_cycle_data)
        db.add(db_campus_cycle)
        db.commit()
        db.refresh(db_campus_cycle)
        return db_campus_cycle
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This admission cycle is already assigned to this campus",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error assigning cycle to campus: {str(e)}",
        )


@admission_router.patch(
    "/campus/{campus_id}/cycles/{campus_cycle_id}",
    response_model=CampusAdmissionCycleResponse
)
def update_campus_admission_cycle(
    campus_id: UUID,
    campus_cycle_id: UUID,
    campus_cycle_update: CampusAdmissionCycleUpdate,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Update a campus admission cycle (e.g., close campus independently).
    
    Both institute admins and campus admins (for their assigned campus) can update.
    Useful for closing specific campuses due to capacity or emergency.
    """
    # Verify campus exists
    campus = db.query(Campus).filter(Campus.id == campus_id).first()
    if not campus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus not found",
        )
    
    # Check if staff can access the campus (works for both institute admin and campus admin)
    if not can_access_campus(campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get campus admission cycle and verify it belongs to this campus
    db_campus_cycle = db.query(CampusAdmissionCycle).filter(
        CampusAdmissionCycle.id == campus_cycle_id,
        CampusAdmissionCycle.campus_id == campus_id
    ).first()
    
    if not db_campus_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus admission cycle not found for this campus",
        )
    
    # Update fields
    update_data = campus_cycle_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_campus_cycle, field, value)
    
    try:
        db.commit()
        db.refresh(db_campus_cycle)
        return db_campus_cycle
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating campus admission cycle: {str(e)}",
        )


@admission_router.delete(
    "/campus/{campus_id}/cycles/{campus_cycle_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def remove_cycle_from_campus(
    campus_id: UUID,
    campus_cycle_id: UUID,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Remove an admission cycle from a campus.
    
    Both institute admins and campus admins (for their assigned campus) can remove.
    This will also cascade delete all program cycles for this campus-cycle combination.
    """
    # Verify campus exists
    campus = db.query(Campus).filter(Campus.id == campus_id).first()
    if not campus:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus not found",
        )
    
    # Check if staff can access the campus (works for both institute admin and campus admin)
    if not can_access_campus(campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get campus admission cycle and verify it belongs to this campus
    db_campus_cycle = db.query(CampusAdmissionCycle).filter(
        CampusAdmissionCycle.id == campus_cycle_id,
        CampusAdmissionCycle.campus_id == campus_id
    ).first()
    
    if not db_campus_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus admission cycle not found for this campus",
        )
    
    try:
        db.delete(db_campus_cycle)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing cycle from campus: {str(e)}",
        )


# ==================== PROGRAM ADMISSION CYCLE ENDPOINTS ====================


@admission_router.get(
    "/campus-cycle/{campus_cycle_id}/program-cycles",
    response_model=List[ProgramAdmissionCycleDetailResponse]
)
def list_program_cycles(
    campus_cycle_id: UUID,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    List all programs in a campus admission cycle with detailed program info.
    
    Staff can access if they have access to the campus.
    Returns seat allocation with nested program details.
    """
    # Get campus admission cycle
    campus_cycle = db.query(CampusAdmissionCycle).filter(
        CampusAdmissionCycle.id == campus_cycle_id
    ).first()
    
    if not campus_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus admission cycle not found",
        )
    
    # Check if staff can access the campus
    if not can_access_campus(campus_cycle.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get all program cycles with program details
    from app.database.models.institute import Program
    program_cycles = (
        db.query(ProgramAdmissionCycle)
        .join(Program, ProgramAdmissionCycle.program_id == Program.id)
        .filter(ProgramAdmissionCycle.campus_admission_cycle_id == campus_cycle_id)
        .order_by(ProgramAdmissionCycle.created_at.desc())
        .all()
    )
    
    # Build detailed response
    result = []
    for program_cycle in program_cycles:
        result.append(
            ProgramAdmissionCycleDetailResponse(
                id=program_cycle.id,
                campus_admission_cycle_id=program_cycle.campus_admission_cycle_id,
                total_seats=program_cycle.total_seats,
                seats_filled=program_cycle.seats_filled,
                description=program_cycle.description,
                custom_metadata=program_cycle.custom_metadata,
                is_active=program_cycle.is_active,
                created_at=program_cycle.created_at,
                updated_at=program_cycle.updated_at,
                program=program_cycle.program,  # SQLAlchemy relationship
            )
        )
    
    return result


@admission_router.get(
    "/campus-cycle/{campus_cycle_id}/program-cycles/{program_cycle_id}",
    response_model=ProgramAdmissionCycleWithQuotasResponse
)
def get_program_cycle_detail(
    campus_cycle_id: UUID,
    program_cycle_id: UUID,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific program cycle including all quotas.
    
    Staff can access if they have access to the campus.
    Returns complete program cycle details with nested program and quota information.
    """
    # Get campus admission cycle
    campus_cycle = db.query(CampusAdmissionCycle).filter(
        CampusAdmissionCycle.id == campus_cycle_id
    ).first()
    
    if not campus_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus admission cycle not found",
        )
    
    # Check if staff can access the campus
    if not can_access_campus(campus_cycle.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get program cycle with program details
    from app.database.models.institute import Program
    program_cycle = (
        db.query(ProgramAdmissionCycle)
        .join(Program, ProgramAdmissionCycle.program_id == Program.id)
        .filter(
            ProgramAdmissionCycle.id == program_cycle_id,
            ProgramAdmissionCycle.campus_admission_cycle_id == campus_cycle_id
        )
        .first()
    )
    
    if not program_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program cycle not found in this campus cycle",
        )
    
    # Get all quotas for this program cycle
    quotas = (
        db.query(ProgramQuota)
        .filter(ProgramQuota.program_cycle_id == program_cycle_id)
        .order_by(ProgramQuota.priority_order, ProgramQuota.created_at)
        .all()
    )
    
    # Build detailed response
    return ProgramAdmissionCycleWithQuotasResponse(
        id=program_cycle.id,
        campus_admission_cycle_id=program_cycle.campus_admission_cycle_id,
        total_seats=program_cycle.total_seats,
        seats_filled=program_cycle.seats_filled,
        description=program_cycle.description,
        custom_metadata=program_cycle.custom_metadata,
        is_active=program_cycle.is_active,
        created_at=program_cycle.created_at,
        updated_at=program_cycle.updated_at,
        program=program_cycle.program,  # SQLAlchemy relationship
        quotas=quotas,  # All quotas for this program cycle
    )


@admission_router.post(
    "/campus-cycle/{campus_cycle_id}/program-cycles",
    response_model=ProgramAdmissionCycleResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_program_to_cycle(
    campus_cycle_id: UUID,
    program_cycle: ProgramAdmissionCycleCreate,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Add a program to a campus admission cycle with seat allocation.
    
    Both institute admins and campus admins (for their assigned campus) can add programs.
    Program must belong to the same institute.
    """
    # Get campus admission cycle
    campus_cycle = db.query(CampusAdmissionCycle).filter(
        CampusAdmissionCycle.id == campus_cycle_id
    ).first()
    
    if not campus_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus admission cycle not found",
        )
    
    # Check if staff can access the campus (works for both institute admin and campus admin)
    if not can_access_campus(campus_cycle.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Verify program exists and belongs to staff's institute
    from app.database.models.institute import Program
    program = db.query(Program).filter(Program.id == program_cycle.program_id).first()
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )
    
    if not can_access_institute(program.institute_id, staff):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this program",
        )
    
    # Extract quotas from request
    quotas_data = program_cycle.quotas
    
    # Create program cycle (exclude quotas from model_dump)
    program_cycle_data = program_cycle.model_dump(exclude={'quotas'})
    program_cycle_data['campus_admission_cycle_id'] = campus_cycle_id
    
    try:
        # Create program cycle
        db_program_cycle = ProgramAdmissionCycle(**program_cycle_data)
        db.add(db_program_cycle)
        db.flush()  # Flush to get the ID without committing
        
        # Create all quotas for this program cycle
        for quota_data in quotas_data:
            quota_dict = quota_data.model_dump()
            quota_dict['program_cycle_id'] = db_program_cycle.id
            quota_dict['seats_filled'] = 0  # Initialize with 0
            quota_dict['status'] = QuotaStatus.ACTIVE  # Default status
            
            db_quota = ProgramQuota(**quota_dict)
            db.add(db_quota)
        
        db.commit()
        db.refresh(db_program_cycle)
        return db_program_cycle
    except IntegrityError as e:
        db.rollback()
        # Check if it's duplicate program or duplicate quota type
        if "uq_campus_cycle_program" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This program is already added to this campus cycle",
            )
        elif "uq_program_cycle_quota_type" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Duplicate quota type detected. Each quota type must be unique.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Integrity constraint violation: {str(e)}",
            )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding program to cycle: {str(e)}",
        )


@admission_router.patch(
    "/campus-cycle/{campus_cycle_id}/program-cycles/{program_cycle_id}",
    response_model=ProgramAdmissionCycleResponse
)
def update_program_cycle(
    campus_cycle_id: UUID,
    program_cycle_id: UUID,
    program_cycle_update: ProgramAdmissionCycleUpdate,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Update a program cycle (e.g., change seat allocation).
    
    Both institute admins and campus admins (for their assigned campus) can update.
    """
    # Get campus admission cycle
    campus_cycle = db.query(CampusAdmissionCycle).filter(
        CampusAdmissionCycle.id == campus_cycle_id
    ).first()
    
    if not campus_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus admission cycle not found",
        )
    
    # Check if staff can access the campus
    if not can_access_campus(campus_cycle.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get program cycle and verify it belongs to this campus-cycle
    db_program_cycle = db.query(ProgramAdmissionCycle).filter(
        ProgramAdmissionCycle.id == program_cycle_id,
        ProgramAdmissionCycle.campus_admission_cycle_id == campus_cycle_id
    ).first()

    if not db_program_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program cycle not found for this campus cycle",
        )

    # Update fields
    update_data = program_cycle_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_program_cycle, field, value)

    try:
        db.commit()
        db.refresh(db_program_cycle)
        return db_program_cycle
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating program cycle: {str(e)}",
        )


@admission_router.delete(
    "/campus-cycle/{campus_cycle_id}/program-cycles/{program_cycle_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def remove_program_from_cycle(
    campus_cycle_id: UUID,
    program_cycle_id: UUID,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Remove a program from a campus admission cycle.
    
    Both institute admins and campus admins (for their assigned campus) can delete.
    This will also cascade delete all quotas for this program cycle.
    """
    # Get campus admission cycle
    campus_cycle = db.query(CampusAdmissionCycle).filter(
        CampusAdmissionCycle.id == campus_cycle_id
    ).first()
    
    if not campus_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus admission cycle not found",
        )
    
    # Check if staff can access the campus
    if not can_access_campus(campus_cycle.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get program cycle and verify it belongs to this campus-cycle
    db_program_cycle = db.query(ProgramAdmissionCycle).filter(
        ProgramAdmissionCycle.id == program_cycle_id,
        ProgramAdmissionCycle.campus_admission_cycle_id == campus_cycle_id
    ).first()

    if not db_program_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program cycle not found for this campus cycle",
        )

    try:
        db.delete(db_program_cycle)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing program from cycle: {str(e)}",
        )


# ==================== PROGRAM QUOTA ENDPOINTS ====================


@admission_router.get(
    "/program-cycle/{program_cycle_id}/quotas",
    response_model=List[ProgramQuotaResponse]
)
def list_program_quotas(
    program_cycle_id: UUID,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    List all quotas for a program cycle.
    
    Staff can access if they have access to the campus.
    Returns all quota types with seat allocation.
    """
    # Get program cycle
    program_cycle = db.query(ProgramAdmissionCycle).filter(
        ProgramAdmissionCycle.id == program_cycle_id
    ).first()
    
    if not program_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program cycle not found",
        )
    
    # Get campus admission cycle to check campus access
    campus_cycle = db.query(CampusAdmissionCycle).filter(
        CampusAdmissionCycle.id == program_cycle.campus_admission_cycle_id
    ).first()
    
    if not campus_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus admission cycle not found",
        )
    
    # Check if staff can access the campus
    if not can_access_campus(campus_cycle.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get all quotas for this program cycle
    quotas = db.query(ProgramQuota).filter(
        ProgramQuota.program_cycle_id == program_cycle_id
    ).order_by(ProgramQuota.priority_order, ProgramQuota.created_at).all()
    
    return quotas


@admission_router.post(
    "/program-cycle/{program_cycle_id}/quotas",
    response_model=ProgramQuotaResponse,
    status_code=status.HTTP_201_CREATED
)
def create_program_quota(
    program_cycle_id: UUID,
    quota: ProgramQuotaCreate,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Create a quota for a program cycle.
    
    Both institute admins and campus admins (for their assigned campus) can create quotas.
    """
    # Get program cycle
    program_cycle = db.query(ProgramAdmissionCycle).filter(
        ProgramAdmissionCycle.id == program_cycle_id
    ).first()
    
    if not program_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program cycle not found",
        )
    
    # Get campus admission cycle to check campus access
    campus_cycle = db.query(CampusAdmissionCycle).filter(
        CampusAdmissionCycle.id == program_cycle.campus_admission_cycle_id
    ).first()
    
    if not campus_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus admission cycle not found",
        )
    
    # Check if staff can access the campus
    if not can_access_campus(campus_cycle.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Create quota
    quota_data = quota.model_dump()
    quota_data['program_cycle_id'] = program_cycle_id
    
    try:
        db_quota = ProgramQuota(**quota_data)
        db.add(db_quota)
        db.commit()
        db.refresh(db_quota)
        return db_quota
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This quota type already exists for this program cycle",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating program quota: {str(e)}",
        )


@admission_router.patch(
    "/program-cycle/{program_cycle_id}/quotas/{quota_id}",
    response_model=ProgramQuotaResponse
)
def update_program_quota(
    program_cycle_id: UUID,
    quota_id: UUID,
    quota_update: ProgramQuotaUpdate,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Update a program quota.
    
    Both institute admins and campus admins (for their assigned campus) can update.
    """
    # Get program cycle
    program_cycle = db.query(ProgramAdmissionCycle).filter(
        ProgramAdmissionCycle.id == program_cycle_id
    ).first()
    
    if not program_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program cycle not found",
        )
    
    # Get campus admission cycle to check campus access
    campus_cycle = db.query(CampusAdmissionCycle).filter(
        CampusAdmissionCycle.id == program_cycle.campus_admission_cycle_id
    ).first()
    
    if not campus_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus admission cycle not found",
        )
    
    # Check if staff can access the campus
    if not can_access_campus(campus_cycle.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get quota and verify it belongs to this program cycle
    db_quota = db.query(ProgramQuota).filter(
        ProgramQuota.id == quota_id,
        ProgramQuota.program_cycle_id == program_cycle_id
    ).first()
    
    if not db_quota:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quota not found for this program cycle",
        )

    # Update fields
    update_data = quota_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_quota, field, value)

    try:
        db.commit()
        db.refresh(db_quota)
        return db_quota
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating program quota: {str(e)}",
        )


@admission_router.delete(
    "/program-cycle/{program_cycle_id}/quotas/{quota_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_program_quota(
    program_cycle_id: UUID,
    quota_id: UUID,
    staff: StaffProfile = Depends(get_current_staff),
    db: Session = Depends(get_db),
):
    """
    Delete a program quota.
    
    Both institute admins and campus admins (for their assigned campus) can delete.
    """
    # Get program cycle
    program_cycle = db.query(ProgramAdmissionCycle).filter(
        ProgramAdmissionCycle.id == program_cycle_id
    ).first()
    
    if not program_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program cycle not found",
        )
    
    # Get campus admission cycle to check campus access
    campus_cycle = db.query(CampusAdmissionCycle).filter(
        CampusAdmissionCycle.id == program_cycle.campus_admission_cycle_id
    ).first()
    
    if not campus_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campus admission cycle not found",
        )
    
    # Check if staff can access the campus
    if not can_access_campus(campus_cycle.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    
    # Get quota and verify it belongs to this program cycle
    db_quota = db.query(ProgramQuota).filter(
        ProgramQuota.id == quota_id,
        ProgramQuota.program_cycle_id == program_cycle_id
    ).first()
    
    if not db_quota:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quota not found for this program cycle",
        )

    try:
        db.delete(db_quota)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting program quota: {str(e)}",
        )

