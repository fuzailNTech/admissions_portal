from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from uuid import UUID
from typing import Optional, List

from app.database.config.db import get_db
from app.database.models.institute import Institute, Campus, Program, CampusProgram
from app.database.models.admission import (
    AdmissionCycle,
    CampusAdmissionCycle,
    ProgramAdmissionCycle,
    ProgramQuota,
    CustomFormField,
    ProgramFormField,
)
from app.schema.student.institutes import (
    InstituteBasicInfo,
    InstituteDetailedInfo,
    InstituteListResponse,
    CampusBasicInfo,
    ActiveCycleInfo,
    ActiveCycleDetail,
    ProgramWithOfferings,
    CampusOfferingDetail,
    QuotaDetail,
    CustomFormFieldDetail,
)

institute_router = APIRouter(
    prefix="/institutes",
    tags=["Student Institutes"],
)


# ==================== HELPER FUNCTIONS ====================

def get_active_cycle(db: Session, institute_id: UUID) -> Optional[AdmissionCycle]:
    """Get the currently active/open admission cycle for an institute"""
    return (
        db.query(AdmissionCycle)
        .filter(
            AdmissionCycle.institute_id == institute_id,
            AdmissionCycle.is_published == True,
            AdmissionCycle.status.in_(["OPEN", "UPCOMING"])
        )
        .order_by(AdmissionCycle.application_start_date.desc())
        .first()
    )


# ==================== ENDPOINTS ====================

@institute_router.get("", response_model=InstituteListResponse)
def list_institutes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by institute name (case-insensitive)"),
    institute_type: Optional[List[str]] = Query(None, description="Filter by institute type(s) - supports multiple values"),
    campus_type: Optional[List[str]] = Query(None, description="Filter by campus type(s) - supports multiple values"),
    province_state: Optional[List[str]] = Query(None, description="Filter by province(s)/state(s) - supports multiple values"),
    city: Optional[List[str]] = Query(None, description="Filter by city/cities - supports multiple values"),
    db: Session = Depends(get_db),
):
    """
    List all active institutes with basic information.
    
    Filters:
    - search: Search by institute name (partial, case-insensitive)
    - institute_type: Direct filter on institute (supports multiple values)
    - campus_type, province_state, city: If ANY campus matches, include the institute (support multiple values)
    
    Examples:
    - /institutes?search=government
    - /institutes?city=Lahore&city=Karachi
    - /institutes?campus_type=girls&province_state=Punjab
    - /institutes?institute_type=government&institute_type=private
    
    Students can browse available institutes and filter by location/type.
    """
    # Base query - only active institutes
    query = db.query(Institute).filter(Institute.status == "active")

    # Search by name (partial match, case-insensitive)
    if search:
        query = query.filter(Institute.name.ilike(f"%{search}%"))

    # Direct institute filter (supports multiple values)
    if institute_type:
        query = query.filter(Institute.institute_type.in_(institute_type))

    # Campus-based filters: Include institute if ANY campus matches
    if campus_type or province_state or city:
        # Subquery to find institutes that have at least one matching campus
        campus_subquery = db.query(Campus.institute_id).filter(
            Campus.is_active == True
        )
        
        if campus_type:
            campus_subquery = campus_subquery.filter(Campus.campus_type.in_(campus_type))
        if province_state:
            campus_subquery = campus_subquery.filter(Campus.province_state.in_(province_state))
        if city:
            # For city, use OR condition with ILIKE for case-insensitive partial matching
            from sqlalchemy import or_
            city_conditions = [Campus.city.ilike(f"%{c.strip()}%") for c in city]
            campus_subquery = campus_subquery.filter(or_(*city_conditions))
        
        # Filter institutes that have at least one matching campus
        query = query.filter(Institute.id.in_(campus_subquery))

    # Get total count after all filters
    total = query.count()

    # Get institutes with pagination
    institutes = query.order_by(Institute.name).offset(skip).limit(limit).all()

    # Build response
    institutes_data = []
    for institute in institutes:
        # Get active cycle
        active_cycle = get_active_cycle(db, institute.id)
        active_cycle_info = None
        if active_cycle:
            active_cycle_info = ActiveCycleInfo(
                id=active_cycle.id,
                name=active_cycle.name,
                academic_year=active_cycle.academic_year,
                status=active_cycle.status,
                application_start_date=active_cycle.application_start_date,
                application_end_date=active_cycle.application_end_date,
                is_published=active_cycle.is_published,
            )

        # Get ALL active campuses for this institute
        # Important: Return ALL campuses, not just the filtered ones
        # This gives students complete view of the institute
        campuses_query = db.query(Campus).filter(
            Campus.institute_id == institute.id,
            Campus.is_active == True
        )
        
        campuses = campuses_query.all()
        
        campuses_data = [
            CampusBasicInfo(
                id=campus.id,
                name=campus.name,
                campus_type=campus.campus_type,
                city=campus.city,
                is_active=campus.is_active,
            )
            for campus in campuses
        ]

        # Build institute data
        institute_data = InstituteBasicInfo(
            id=institute.id,
            name=institute.name,
            institute_code=institute.institute_code,
            institute_type=institute.institute_type,
            institute_level=institute.institute_level,
            established_year=institute.established_year,
            active_cycle=active_cycle_info,
            campuses=campuses_data,
        )
        institutes_data.append(institute_data)

    return InstituteListResponse(total=total, institutes=institutes_data)


@institute_router.get("/{institute_id}", response_model=InstituteDetailedInfo)
def get_institute_details(
    institute_id: UUID,
    campus_type: Optional[List[str]] = Query(None, description="Filter by campus type(s) - supports multiple values"),
    province_state: Optional[List[str]] = Query(None, description="Filter by province(s)/state(s) - supports multiple values"),
    city: Optional[List[str]] = Query(None, description="Filter by city/cities - supports multiple values"),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about an institute including:
    - Institute information
    - Active admission cycle
    - Programs with campus offerings, seats, and quotas
    
    Filters:
    - campus_type, province_state, city: Filter campus offerings (supports multiple values)
    - Only programs offered at matching campuses will be included
    
    Examples:
    - /institutes/{id}?campus_type=girls
    - /institutes/{id}?city=Lahore&city=Karachi
    - /institutes/{id}?campus_type=girls&province_state=Punjab
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

    # Get active cycle
    active_cycle = get_active_cycle(db, institute_id)
    
    if not active_cycle:
        # No active admissions - return institute info with empty programs
        return InstituteDetailedInfo(
            id=institute.id,
            name=institute.name,
            institute_code=institute.institute_code,
            institute_type=institute.institute_type,
            institute_level=institute.institute_level,
            established_year=institute.established_year,
            regulatory_body=institute.regulatory_body,
            registration_number=institute.registration_number,
            primary_email=institute.primary_email,
            primary_phone=institute.primary_phone,
            website_url=institute.website_url,
            active_cycle=None,
            programs=[],
        )

    # Build active cycle detail
    active_cycle_detail = ActiveCycleDetail(
        id=active_cycle.id,
        name=active_cycle.name,
        academic_year=active_cycle.academic_year,
        session=active_cycle.session,
        status=active_cycle.status,
        application_start_date=active_cycle.application_start_date,
        application_end_date=active_cycle.application_end_date,
        description=active_cycle.description,
    )

    # Get all programs for this institute
    programs = (
        db.query(Program)
        .filter(Program.institute_id == institute_id, Program.is_active == True)
        .all()
    )

    programs_data = []
    
    for program in programs:
        # Get form fields for this program
        program_form_fields = (
            db.query(ProgramFormField)
            .join(CustomFormField)
            .filter(
                ProgramFormField.program_id == program.id,
                CustomFormField.is_active == True
            )
            .order_by(ProgramFormField.display_order)
            .all()
        )

        form_fields_data = [
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
                options=pff.form_field.options or [],
                is_required=pff.is_required,
                display_order=pff.display_order,
            )
            for pff in program_form_fields
        ]

        # Get campus offerings for this program in the active cycle
        campus_offerings_data = []

        # Get all campuses offering this program (with optional filters)
        campus_query = (
            db.query(CampusProgram)
            .join(Campus)
            .filter(
                CampusProgram.program_id == program.id,
                CampusProgram.is_active == True,
                Campus.is_active == True
            )
        )
        
        # Apply campus filters if provided
        if campus_type:
            campus_query = campus_query.filter(Campus.campus_type.in_(campus_type))
        
        if province_state:
            campus_query = campus_query.filter(Campus.province_state.in_(province_state))
        
        if city:
            # For city, use OR condition with ILIKE for case-insensitive partial matching
            city_conditions = [Campus.city.ilike(f"%{c.strip()}%") for c in city]
            campus_query = campus_query.filter(or_(*city_conditions))
        
        campus_programs = campus_query.all()

        for campus_program in campus_programs:
            campus = campus_program.campus
            
            # Check if campus is participating in this cycle
            campus_cycle = (
                db.query(CampusAdmissionCycle)
                .filter(
                    CampusAdmissionCycle.campus_id == campus.id,
                    CampusAdmissionCycle.admission_cycle_id == active_cycle.id
                )
                .first()
            )

            if not campus_cycle:
                continue  # Campus not participating in this cycle
 
            # Get program admission cycle (seats allocation)
            program_cycle = (
                db.query(ProgramAdmissionCycle)
                .filter(
                    ProgramAdmissionCycle.campus_admission_cycle_id == campus_cycle.id,
                    ProgramAdmissionCycle.program_id == program.id,
                    ProgramAdmissionCycle.is_active == True
                )
                .first()
            )

            if not program_cycle:
                continue  # Program not offered at this campus for this cycle

            # Get quotas
            quotas = (
                db.query(ProgramQuota)
                .filter(ProgramQuota.program_cycle_id == program_cycle.id)
                .order_by(ProgramQuota.priority_order)
                .all()
            )

            quotas_data = [
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
                    eligibility_requirements=quota.eligibility_requirements or {},
                    required_documents=quota.required_documents or [],
                )
                for quota in quotas
            ]

            # Build campus offering
            campus_offering = CampusOfferingDetail(
                campus_id=campus.id,
                campus_name=campus.name,
                campus_type=campus.campus_type,
                campus_code=campus.campus_code,
                city=campus.city,
                address_line=campus.address_line,
                campus_phone=campus.campus_phone,
                campus_email=campus.campus_email,
                admission_open=campus_cycle.is_open,
                closure_reason=campus_cycle.closure_reason,
                total_seats=program_cycle.total_seats,
                seats_filled=program_cycle.seats_filled,
                seats_available=program_cycle.total_seats - program_cycle.seats_filled,
                quotas=quotas_data,
            )
            campus_offerings_data.append(campus_offering)

        # Only include program if it has at least one campus offering
        if campus_offerings_data:
            program_data = ProgramWithOfferings(
                id=program.id,
                name=program.name,
                code=program.code,
                level=program.level,
                category=program.category,
                duration_years=program.duration_years,
                description=program.description,
                custom_form_fields=form_fields_data,
                campus_offerings=campus_offerings_data,
            )
            programs_data.append(program_data)

    # Build final response
    return InstituteDetailedInfo(
        id=institute.id,
        name=institute.name,
        institute_code=institute.institute_code,
        institute_type=institute.institute_type,
        institute_level=institute.institute_level,
        established_year=institute.established_year,
        regulatory_body=institute.regulatory_body,
        registration_number=institute.registration_number,
        primary_email=institute.primary_email,
        primary_phone=institute.primary_phone,
        website_url=institute.website_url,
        active_cycle=active_cycle_detail,
        programs=programs_data,
    )
