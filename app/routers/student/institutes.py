from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from uuid import UUID
from typing import Optional

from app.database.config.db import get_db
from app.database.models.institute import Institute, Campus, Program
from app.database.models.admission import (
    AdmissionCycle,
    ProgramAdmissionCycle,
    ProgramQuota,
    CustomFormField,
    ProgramFormField,
)
from app.schema.student.institutes import (
    InstituteBasicInfo,
    InstituteDetailedInfo,
    InstituteListResponse,
    ProgramBasicInfo,
    ProgramCycleDetail,
    AdmissionCycleDetail,
    QuotaDetail,
    CustomFormFieldDetail,
)

institute_router = APIRouter(
    prefix="/institute",
    tags=["Student Institutes Management"],
)


# ==================== INSTITUTE ENDPOINTS ====================


@institute_router.get("/list", response_model=InstituteListResponse)
def list_institutes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    city: Optional[str] = None,
    province_state: Optional[str] = None,
    institute_type: Optional[str] = None,
    institute_level: Optional[str] = None,
    campus_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    List all active institutes with their campuses.
    Students can browse available institutes and campuses.
    """
    # Base query - only active institutes
    query = db.query(Institute).filter(Institute.status == "active")

    # Apply institute filters
    if institute_type:
        query = query.filter(Institute.institute_type == institute_type)
    if institute_level:
        query = query.filter(Institute.institute_level == institute_level)

    # Get total count
    total = query.count()

    # Get institutes
    institutes = query.order_by(Institute.name).offset(skip).limit(limit).all()

    # Build response with campuses
    institutes_data = []
    for institute in institutes:
        # Get campuses with filters
        campuses_query = db.query(Campus).filter(
            Campus.institute_id == institute.id, Campus.is_active == True
        )

        # Apply campus filters
        if city:
            campuses_query = campuses_query.filter(Campus.city.ilike(f"%{city}%"))
        if province_state:
            campuses_query = campuses_query.filter(
                Campus.province_state == province_state
            )
        if campus_type:
            campuses_query = campuses_query.filter(Campus.campus_type == campus_type)

        campuses = campuses_query.all()

        # Build campus basic info
        from app.schema.student.institutes import CampusBasicInfo

        campuses_data = [
            CampusBasicInfo(
                id=campus.id,
                name=campus.name,
                campus_code=campus.campus_code,
                campus_type=campus.campus_type,
                city=campus.city,
                province_state=campus.province_state,
                country=campus.country,
                is_active=campus.is_active,
            )
            for campus in campuses
        ]

        institute_dict = {
            "id": institute.id,
            "name": institute.name,
            "institute_code": institute.institute_code,
            "institute_type": institute.institute_type,
            "institute_level": institute.institute_level,
            "status": institute.status,
            "campuses": campuses_data,
        }
        institutes_data.append(InstituteBasicInfo(**institute_dict))

    return InstituteListResponse(total=total, institutes=institutes_data)


@institute_router.get("/{institute_id}", response_model=InstituteDetailedInfo)
def get_institute_details(
    institute_id: UUID,
    campus_id: Optional[UUID] = Query(None, description="Filter by specific campus"),
    calendar_id: Optional[UUID] = Query(
        None, description="Filter by specific admission calendar"
    ),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about an institute including:
    - Institute information
    - Campuses with full admission details
    - Programs per campus
    - Admission calendars per campus
    - Quotas and form fields
    """
    # Get institute
    institute = (
        db.query(Institute)
        .filter(Institute.id == institute_id, Institute.status == "active")
        .first()
    )

    if not institute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institute not found or not active",
        )

    # Get active campuses
    campuses_query = db.query(Campus).filter(
        Campus.institute_id == institute_id, Campus.is_active == True
    )

    if campus_id:
        campuses_query = campuses_query.filter(Campus.id == campus_id)

    campuses = campuses_query.all()

    # Build detailed campus info
    from app.schema.student.institutes import CampusDetailedInfo

    campuses_detailed = []

    for campus in campuses:
        # Get published cycles for this campus
        cycles_query = db.query(AdmissionCycle).filter(
            AdmissionCycle.campus_id == campus.id, AdmissionCycle.is_published == True
        )

        if calendar_id:
            cycles_query = cycles_query.filter(AdmissionCycle.id == calendar_id)

        cycles = cycles_query.order_by(AdmissionCycle.created_at.desc()).all()

        # Build cycle details for this campus
        cycle_details = [
            AdmissionCycleDetail(
                id=cycle.id,
                name=cycle.name,
                academic_year=cycle.academic_year,
                session=cycle.session,
                status=cycle.status,
                application_start_date=cycle.application_start_date,
                application_end_date=cycle.application_end_date,
                description=cycle.description,
                is_published=cycle.is_published,
            )
            for cycle in cycles
        ]

        # Get programs for this campus
        programs_data = []

        for cycle in cycles:
            # Get cycle programs
            cycle_programs = (
                db.query(ProgramAdmissionCycle)
                .options(
                    joinedload(ProgramAdmissionCycle.program),
                    joinedload(ProgramAdmissionCycle.quotas),
                    joinedload(ProgramAdmissionCycle.program_form_fields).joinedload(
                        ProgramFormField.form_field
                    ),
                )
                .filter(
                    ProgramAdmissionCycle.admission_cycle_id == cycle.id,
                    ProgramAdmissionCycle.is_active == True,
                )
                .all()
            )

            for cp in cycle_programs:
                # Calculate seats available
                seats_available = cp.total_seats - cp.seats_filled

                # Get quotas with availability
                quota_details = [
                    QuotaDetail(
                        id=quota.id,
                        quota_type=quota.quota_type,
                        quota_name=quota.quota_name,
                        allocated_seats=quota.allocated_seats,
                        seats_filled=quota.seats_filled,
                        seats_available=quota.allocated_seats - quota.seats_filled,
                        minimum_marks=quota.minimum_marks,
                        priority_order=quota.priority_order,
                        status=quota.status,
                        description=quota.description,
                        eligibility_requirements=quota.eligibility_requirements,
                        required_documents=quota.required_documents,
                    )
                    for quota in (cp.quotas or [])
                ]

                # Get custom form fields
                form_fields = [
                    CustomFormFieldDetail(
                        id=pff.form_field.id,
                        field_name=pff.form_field.field_name,
                        label=pff.form_field.label,
                        field_type=pff.form_field.field_type,
                        placeholder=pff.form_field.placeholder,
                        help_text=pff.form_field.help_text,
                        default_value=pff.form_field.default_value,
                        min_length=pff.form_field.min_length,
                        max_length=pff.form_field.max_length,
                        min_value=pff.form_field.min_value,
                        max_value=pff.form_field.max_value,
                        pattern=pff.form_field.pattern,
                        options=pff.form_field.options,
                        is_required=pff.is_required,
                    )
                    for pff in (cp.program_form_fields or [])
                ]

                program_detail = ProgramCycleDetail(
                    id=cp.id,
                    program_id=cp.program.id,
                    program_name=cp.program.name,
                    program_code=cp.program.code,
                    program_level=cp.program.level,
                    program_category=cp.program.category,
                    total_seats=cp.total_seats,
                    seats_filled=cp.seats_filled,
                    seats_available=seats_available,
                    minimum_marks_required=cp.minimum_marks_required,
                    eligibility_criteria=cp.eligibility_criteria,
                    description=cp.description,
                    quotas=quota_details,
                    custom_form_fields=form_fields,
                    is_active=cp.is_active,
                )
                programs_data.append(program_detail)

        # Build detailed campus info
        campus_detailed = CampusDetailedInfo(
            id=campus.id,
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
            admission_cycles=cycle_details,
            programs=programs_data,
        )
        campuses_detailed.append(campus_detailed)

    # Build response
    return InstituteDetailedInfo(
        id=institute.id,
        name=institute.name,
        institute_code=institute.institute_code,
        institute_type=institute.institute_type,
        institute_level=institute.institute_level,
        status=institute.status,
        registration_number=institute.registration_number,
        regulatory_body=institute.regulatory_body,
        established_year=institute.established_year,
        primary_email=institute.primary_email,
        primary_phone=institute.primary_phone,
        website_url=institute.website_url,
        campuses=campuses_detailed,
    )
