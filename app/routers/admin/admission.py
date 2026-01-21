from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.admission import (
    AdmissionCycle,
    ProgramAdmissionCycle,
    ProgramQuota,
    CustomFormField,
    ProgramFormField,
)
from app.database.models.auth import User
from app.schema.admin.admission import (
    # AdmissionCycle
    AdmissionCycleCreate,
    AdmissionCycleUpdate,
    AdmissionCycleResponse,
    # ProgramAdmissionCycle
    ProgramAdmissionCycleCreate,
    ProgramAdmissionCycleUpdate,
    ProgramAdmissionCycleResponse,
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
)
from app.utils.auth import get_current_user

admission_router = APIRouter(
    prefix="/admission",
    tags=["Admin Admission Management"],
)


# ==================== ADMISSION CYCLE ENDPOINTS ====================


@admission_router.post(
    "/cycles",
    response_model=AdmissionCycleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admission_cycle(
    cycle: AdmissionCycleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new admission cycle."""
    try:
        db_cycle = AdmissionCycle(**cycle.model_dump(), created_by=current_user.id)
        db.add(db_cycle)
        db.commit()
        db.refresh(db_cycle)
        return db_cycle
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an admission cycle."""
    db_cycle = db.query(AdmissionCycle).filter(AdmissionCycle.id == cycle_id).first()
    if not db_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission cycle with id {cycle_id} not found",
        )

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an admission cycle."""
    db_cycle = db.query(AdmissionCycle).filter(AdmissionCycle.id == cycle_id).first()
    if not db_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission cycle with id {cycle_id} not found",
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


# ==================== PROGRAM ADMISSION CYCLE ENDPOINTS ====================


@admission_router.post(
    "/program-cycles",
    response_model=ProgramAdmissionCycleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_program_cycle(
    program_cycle: ProgramAdmissionCycleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a program to an admission cycle."""
    try:
        db_program_cycle = ProgramAdmissionCycle(**program_cycle.model_dump())
        db.add(db_program_cycle)
        db.commit()
        db.refresh(db_program_cycle)
        return db_program_cycle
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This program is already added to this cycle",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating program cycle: {str(e)}",
        )


@admission_router.patch(
    "/program-cycles/{program_cycle_id}", response_model=ProgramAdmissionCycleResponse
)
def update_program_cycle(
    program_cycle_id: UUID,
    program_cycle_update: ProgramAdmissionCycleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a program cycle."""
    db_program_cycle = (
        db.query(ProgramAdmissionCycle)
        .filter(ProgramAdmissionCycle.id == program_cycle_id)
        .first()
    )

    if not db_program_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program cycle with id {program_cycle_id} not found",
        )

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
    "/program-cycles/{program_cycle_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_program_cycle(
    program_cycle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a program from an admission cycle."""
    db_program_cycle = (
        db.query(ProgramAdmissionCycle)
        .filter(ProgramAdmissionCycle.id == program_cycle_id)
        .first()
    )

    if not db_program_cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program cycle with id {program_cycle_id} not found",
        )

    try:
        db.delete(db_program_cycle)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting program cycle: {str(e)}",
        )


# ==================== PROGRAM QUOTA ENDPOINTS ====================


@admission_router.post(
    "/quotas", response_model=ProgramQuotaResponse, status_code=status.HTTP_201_CREATED
)
def create_program_quota(
    quota: ProgramQuotaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a quota for a calendar program."""
    try:
        db_quota = ProgramQuota(**quota.model_dump())
        db.add(db_quota)
        db.commit()
        db.refresh(db_quota)
        return db_quota
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This quota type already exists for this program",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating program quota: {str(e)}",
        )


@admission_router.patch("/quotas/{quota_id}", response_model=ProgramQuotaResponse)
def update_program_quota(
    quota_id: UUID,
    quota_update: ProgramQuotaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a program quota."""
    db_quota = db.query(ProgramQuota).filter(ProgramQuota.id == quota_id).first()
    if not db_quota:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program quota with id {quota_id} not found",
        )

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


@admission_router.delete("/quotas/{quota_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program_quota(
    quota_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a program quota."""
    db_quota = db.query(ProgramQuota).filter(ProgramQuota.id == quota_id).first()
    if not db_quota:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program quota with id {quota_id} not found",
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


# ==================== CUSTOM FORM FIELD ENDPOINTS ====================


@admission_router.post(
    "/form-fields",
    response_model=CustomFormFieldResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_custom_form_field(
    form_field: CustomFormFieldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a custom form field for an institute."""
    try:
        db_form_field = CustomFormField(
            **form_field.model_dump(), created_by=current_user.id
        )
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a custom form field."""
    db_form_field = (
        db.query(CustomFormField).filter(CustomFormField.id == form_field_id).first()
    )
    if not db_form_field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custom form field with id {form_field_id} not found",
        )

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a custom form field."""
    db_form_field = (
        db.query(CustomFormField).filter(CustomFormField.id == form_field_id).first()
    )
    if not db_form_field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custom form field with id {form_field_id} not found",
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


@admission_router.post(
    "/program-form-fields",
    response_model=ProgramFormFieldResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_form_field_to_program(
    program_form_field: ProgramFormFieldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign a custom form field to a program."""
    try:
        db_program_form_field = ProgramFormField(**program_form_field.model_dump())
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
    "/program-form-fields/{program_form_field_id}",
    response_model=ProgramFormFieldResponse,
)
def update_program_form_field(
    program_form_field_id: UUID,
    program_form_field_update: ProgramFormFieldUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update program form field settings."""
    db_program_form_field = (
        db.query(ProgramFormField)
        .filter(ProgramFormField.id == program_form_field_id)
        .first()
    )

    if not db_program_form_field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program form field with id {program_form_field_id} not found",
        )

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
    "/program-form-fields/{program_form_field_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_form_field_from_program(
    program_form_field_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a form field from a program."""
    db_program_form_field = (
        db.query(ProgramFormField)
        .filter(ProgramFormField.id == program_form_field_id)
        .first()
    )

    if not db_program_form_field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program form field with id {program_form_field_id} not found",
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
