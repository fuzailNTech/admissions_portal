from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Tuple, Optional
from uuid import UUID

from app.database.config.db import get_db
from app.database.models.workflow import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowCatalog,
)
from app.database.models.institute import Institute, Program, Campus
from app.database.models.auth import User
from app.database.models.student import (
    StudentProfile,
    StudentGuardian,
    StudentAcademicRecord,
)
from app.database.models.application import (
    Application,
    ApplicationSnapshot,
    ApplicationGuardianSnapshot,
    ApplicationAcademicSnapshot,
    ApplicationStatusHistory,
    ApplicationStatus,
    VerificationStatus,
)
from app.database.models.admission import (
    ProgramAdmissionCycle,
    CampusAdmissionCycle,
    AdmissionCycle,
    ProgramQuota,
    AdmissionCycleStatus,
)
from app.schema.student.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationSubmitRequest,
    ApplicationSubmitResponse,
)
from app.utils.auth import get_current_active_user, get_password_hash, generate_strong_password
from app.utils.admission import generate_application_number
from datetime import datetime
from app.bpm.engine import (
    load_spec_from_xml,
    create_workflow_instance,
    run_service_tasks,
    dumps_wf,
)

application_router = APIRouter(
    prefix="/application",
    tags=["Student - Application Management"],
)


def build_subprocess_registry(
    subprocess_refs: list, db: Session
) -> Dict[str, Tuple[str, str]]:
    """
    Build subprocess registry for SpiffWorkflow.

    Args:
        subprocess_refs: List of subprocess references from workflow definition
        db: Database session

    Returns:
        Dict mapping calledElement -> (subprocess_xml, subprocess_id)
        e.g., {"communication.send_email_1": ("<xml>...</xml>", "communication.send_email_1")}
    """
    registry = {}

    for ref in subprocess_refs:
        subflow_key = ref.get("subflow_key")
        version = ref.get("version")
        called_element = ref.get("calledElement")

        if not all([subflow_key, version, called_element]):
            continue

        # Look up subworkflow in catalog
        subworkflow = (
            db.query(WorkflowCatalog)
            .filter(
                WorkflowCatalog.subflow_key == subflow_key,
                WorkflowCatalog.version == version,
                WorkflowCatalog.published == True,
            )
            .first()
        )

        if not subworkflow:
            raise ValueError(
                f"Subworkflow '{subflow_key}_{version}' not found in catalog or not published"
            )

        registry[called_element] = (subworkflow.bpmn_xml, subworkflow.process_id)

    return registry


def get_default_initial_data() -> dict:
    """Generate dummy initial data for workflow execution."""
    return {
        "email": "applicant@example.com",
        "user_id": "12345",
        "application": {
            "id": "app-001",
            "name": "John Doe",
            "marks": 85,
            "documents": [
                {"type": "transcript", "status": "uploaded"},
                {"type": "certificate", "status": "uploaded"},
            ],
        },
        "documents": [
            {"type": "transcript", "url": "https://example.com/transcript.pdf"},
            {"type": "certificate", "url": "https://example.com/certificate.pdf"},
        ],
        "policy": {
            "verification": {"limit": 3},
            "fee": {"base": 1000, "currency": "USD"},
        },
    }


@application_router.post(
    "", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED
)
def create_application(
    application: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new application and start workflow instance.
    Uses the active/published workflow definition for the institute.
    """
    try:
        # Verify institute exists
        institute = (
            db.query(Institute).filter(Institute.id == application.institute_id).first()
        )
        if not institute:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Institute with id {application.institute_id} not found",
            )

        # Get active/published workflow definition for the institute
        workflow_def = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.institute_id == application.institute_id,
                WorkflowDefinition.published == True,
                WorkflowDefinition.active == True,
            )
            .order_by(WorkflowDefinition.version.desc())
            .first()
        )

        if not workflow_def:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active/published workflow definition found for institute {application.institute_id}",
            )

        # Build subprocess registry
        subprocess_refs = workflow_def.subprocess_refs or []
        try:
            subprocess_registry = build_subprocess_registry(subprocess_refs, db)
            print(f"Built subprocess registry with {len(subprocess_registry)} entries:")
            for called_element, (xml, process_id) in subprocess_registry.items():
                print(f"  {called_element} -> process_id: {process_id}")
                # Verify the calledElement matches the process_id in the subprocess XML
                if process_id != called_element:
                    print(
                        f"  ⚠️  WARNING: calledElement '{called_element}' != process_id '{process_id}'"
                    )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        # Load BPMN spec with subprocesses
        try:
            spec, subprocess_specs = load_spec_from_xml(
                xml_string=workflow_def.bpmn_xml,
                spec_name=workflow_def.process_id,
                subprocess_registry=(
                    subprocess_registry if subprocess_registry else None
                ),
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error loading BPMN spec: {str(e)}",
            )

        # Prepare initial data (merge dummy data with provided data)
        default_data = get_default_initial_data()
        initial_data = {**default_data, **(application.initial_data or {})}

        # Create workflow instance with subprocess specs
        workflow = create_workflow_instance(
            spec,
            subprocess_specs=subprocess_specs if subprocess_specs else None,
            data=initial_data,
        )

        # Create workflow instance record
        wf_instance = WorkflowInstance(
            institute_id=application.institute_id,
            workflow_definition_id=workflow_def.id,
            business_key=application.business_key,
            definition=workflow_def.process_id,
            state=dumps_wf(workflow),
            status="running",
        )

        db.add(wf_instance)
        db.flush()  # Flush to get the ID

        # Run the workflow
        try:
            should_persist, waiting_task_ids = run_service_tasks(
                wf=workflow,
                db=db,
                wf_row=wf_instance,
                user=current_user,
                auto_persist=False,  # We'll persist manually
            )

            # Update workflow instance with current state
            wf_instance.state = dumps_wf(workflow)
            wf_instance.current_tasks = waiting_task_ids

            if workflow.is_completed():
                wf_instance.status = "completed"
                from datetime import datetime

                wf_instance.completed_at = datetime.utcnow()

            db.commit()
            db.refresh(wf_instance)

        except Exception as e:
            # Mark workflow as failed
            wf_instance.status = "failed"
            wf_instance.error_message = str(e)
            wf_instance.state = dumps_wf(workflow)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error executing workflow: {str(e)}",
            )

        return wf_instance

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating application: {str(e)}",
        )


@application_router.get(
    "/institute/{institute_id}", response_model=list[ApplicationResponse]
)
def list_applications(
    institute_id: UUID,
    skip: int = 0,
    limit: int = 100,
    status: str = None,
    db: Session = Depends(get_db),
):
    """
    List all applications (workflow instances) for an institute.
    """
    # Verify institute exists
    institute = db.query(Institute).filter(Institute.id == institute_id).first()
    if not institute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institute with id {institute_id} not found",
        )

    query = db.query(WorkflowInstance).filter(
        WorkflowInstance.institute_id == institute_id
    )

    # Apply filters
    if status:
        query = query.filter(WorkflowInstance.status == status)

    # Order by created_at descending
    query = query.order_by(WorkflowInstance.created_at.desc())

    # Apply pagination
    applications = query.offset(skip).limit(limit).all()

    return applications


@application_router.get("/{application_id}", response_model=ApplicationResponse)
def get_application(
    application_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get a specific application (workflow instance) by ID.
    """
    application = (
        db.query(WorkflowInstance).filter(WorkflowInstance.id == application_id).first()
    )

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with id {application_id} not found",
        )

    return application


@application_router.post("/submit", response_model=ApplicationSubmitResponse, status_code=status.HTTP_201_CREATED)
def submit_student_application(
    request: ApplicationSubmitRequest,
    db: Session = Depends(get_db),
):
    """
    Submit student application(s) to one or more programs.
    
    This endpoint allows students to apply without prior login. It handles:
    - New student registration (creates user account with generated password)
    - Returning student applications (uses existing profile)
    - Multiple program applications in a single submission
    - Creates immutable snapshots of submitted data for each application
    
    **Flow:**
    1. Validates all program targets (cycles, quotas, seats availability)
    2. Creates or retrieves student profile (based on identity document)
    3. Creates application snapshots (one per program)
    4. Generates unique application numbers
    5. Sends email with credentials and confirmation
    
    **Authentication:**
    - No login required to submit
    - Credentials sent via email for future tracking
    - Students login using identity document number + password
    
    **Identity Document:**
    - Primary identifier for students
    - Format: XXXXX-XXXXXXX-X (CNIC or B-Form)
    - Prevents duplicate registrations
    
    **All-or-Nothing:**
    - All applications succeed together or all fail
    - Ensures data consistency across multiple program applications
    """
    try:
        # Start transaction
        with db.begin_nested():
            
            # ==================== STEP 1: VALIDATE ALL PROGRAM TARGETS ====================
            # Store resolved program cycles for each application
            program_cycles_map = {}  # Key: index, Value: (program_cycle, admission_cycle)
            
            for idx, program_data in enumerate(request.applied_programs):
                
                # Check institute exists
                institute = db.query(Institute).filter(
                    Institute.id == program_data.institute_id
                ).first()
                if not institute:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Institute with id {program_data.institute_id} not found"
                    )
                
                # Check program exists and belongs to institute
                program = db.query(Program).filter(
                    Program.id == program_data.program_id,
                    Program.institute_id == program_data.institute_id
                ).first()
                if not program:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Program not found or does not belong to this institute"
                    )
                
                # Check campus exists and belongs to institute
                campus = db.query(Campus).filter(
                    Campus.id == program_data.preferred_campus_id,
                    Campus.institute_id == program_data.institute_id
                ).first()
                if not campus:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Campus not found or does not belong to this institute"
                    )
                
                # Get active/open admission cycle for the institute
                admission_cycle = db.query(AdmissionCycle).filter(
                    AdmissionCycle.institute_id == program_data.institute_id,
                    AdmissionCycle.status == AdmissionCycleStatus.OPEN,
                    AdmissionCycle.is_published == True
                ).first()
                if not admission_cycle:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No active admission cycle found for this institute"
                    )
                
                # Check if within application date range
                now = datetime.now(admission_cycle.application_start_date.tzinfo)
                if now < admission_cycle.application_start_date:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Application period has not started yet"
                    )
                if now > admission_cycle.application_end_date:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Application period has ended"
                    )
                
                # Get campus admission cycle
                campus_cycle = db.query(CampusAdmissionCycle).filter(
                    CampusAdmissionCycle.campus_id == program_data.preferred_campus_id,
                    CampusAdmissionCycle.admission_cycle_id == admission_cycle.id
                ).first()
                if not campus_cycle:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Campus is not participating in the current admission cycle"
                    )
                
                # Check if campus is open for applications
                if not campus_cycle.is_open:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Campus is not accepting applications. Reason: {campus_cycle.closure_reason or 'Not specified'}"
                    )
                
                # Find program cycle for this program + campus combination
                program_cycle = db.query(ProgramAdmissionCycle).filter(
                    ProgramAdmissionCycle.program_id == program_data.program_id,
                    ProgramAdmissionCycle.campus_admission_cycle_id == campus_cycle.id
                ).first()
                if not program_cycle:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="This program is not offered at the selected campus for the current admission cycle"
                    )
                
                # Check if program cycle is active
                if not program_cycle.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Program is not currently accepting applications"
                    )
                
                # Check quota exists and is valid
                quota = db.query(ProgramQuota).filter(
                    ProgramQuota.id == program_data.quota_id,
                    ProgramQuota.program_cycle_id == program_cycle.id
                ).first()
                if not quota:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Quota not found or does not belong to this program cycle"
                    )
                
                # Store resolved program cycle and admission cycle for later use
                program_cycles_map[idx] = (program_cycle, admission_cycle)
            
            # ==================== STEP 2: HANDLE USER & PROFILE ====================
            
            # Check if student exists by identity document
            existing_profile = db.query(StudentProfile).filter(
                StudentProfile.identity_doc_number == request.student_profile.identity_doc_number
            ).first()
            
            student_password = None
            is_new_student = False
            
            if existing_profile:
                # ========== RETURNING STUDENT ==========
                user = existing_profile.user
                
                # Security check: verify date of birth matches
                if existing_profile.date_of_birth != request.student_profile.date_of_birth:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Identity document already registered with different date of birth. Please contact support."
                    )
                
                # Security check: verify father name matches
                if existing_profile.father_name != request.student_profile.father_name:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Identity document already registered with different father name. Please contact support."
                    )
                
                # Handle email change
                if user.email != request.student_profile.primary_email:
                    # Check if new email is already taken by someone else
                    email_taken = db.query(User).filter(
                        User.email == request.student_profile.primary_email,
                        User.id != user.id
                    ).first()
                    
                    if email_taken:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This email is already registered with another account. Please use a different email."
                        )
                    
                    # Update email
                    user.email = request.student_profile.primary_email
                
            else:
                # ========== NEW STUDENT ==========
                is_new_student = True
                
                # Check if email is already taken
                existing_user = db.query(User).filter(
                    User.email == request.student_profile.primary_email
                ).first()
                
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This email is already registered. Please use a different email."
                    )
                
                # Generate password
                student_password = generate_strong_password()
                
                # Create user
                user = User(
                    email=request.student_profile.primary_email,
                    password_hash=get_password_hash(student_password),
                    verified=False,
                    is_active=True
                )
                db.add(user)
                db.flush()
                
                # Create student profile
                profile = StudentProfile(
                    user_id=user.id,
                    first_name=request.student_profile.first_name,
                    last_name=request.student_profile.last_name,
                    father_name=request.student_profile.father_name,
                    gender=request.student_profile.gender,
                    date_of_birth=request.student_profile.date_of_birth,
                    identity_doc_number=request.student_profile.identity_doc_number,
                    identity_doc_type=request.student_profile.identity_doc_type,
                    religion=request.student_profile.religion,
                    nationality=request.student_profile.nationality,
                    is_disabled=request.student_profile.is_disabled,
                    disability_details=request.student_profile.disability_details,
                    primary_email=request.student_profile.primary_email,
                    primary_phone=request.student_profile.primary_phone,
                    alternate_phone=request.student_profile.alternate_phone,
                    street_address=request.student_profile.street_address,
                    city=request.student_profile.city,
                    district=request.student_profile.district,
                    province=request.student_profile.province,
                    postal_code=request.student_profile.postal_code,
                    domicile_province=request.student_profile.domicile_province,
                    domicile_district=request.student_profile.domicile_district,
                    profile_picture_url=request.student_profile.profile_picture_url,
                    identity_doc_url=request.student_profile.identity_doc_url,
                )
                db.add(profile)
                db.flush()
                
                # Create guardian
                guardian = StudentGuardian(
                    student_profile_id=profile.id,
                    guardian_relationship=request.guardian.guardian_relationship,
                    first_name=request.guardian.first_name,
                    last_name=request.guardian.last_name,
                    cnic=request.guardian.cnic,
                    phone_number=request.guardian.phone_number,
                    email=request.guardian.email,
                    occupation=request.guardian.occupation,
                    is_primary=request.guardian.is_primary,
                )
                db.add(guardian)
                
                # Create academic record
                academic_record = StudentAcademicRecord(
                    student_profile_id=profile.id,
                    level=request.academic_record.level,
                    education_group=request.academic_record.education_group,
                    institute_name=request.academic_record.institute_name,
                    board_name=request.academic_record.board_name,
                    roll_number=request.academic_record.roll_number,
                    year_of_passing=request.academic_record.year_of_passing,
                    total_marks=request.academic_record.total_marks,
                    obtained_marks=request.academic_record.obtained_marks,
                    grade=request.academic_record.grade,
                    result_card_url=request.academic_record.result_card_url,
                )
                db.add(academic_record)
                db.flush()
                
                existing_profile = profile
            
            # ==================== STEP 3: CREATE APPLICATIONS ====================
            
            application_numbers = []
            
            for idx, program_data in enumerate(request.applied_programs):
                # Get resolved program cycle and admission cycle from validation
                program_cycle, admission_cycle = program_cycles_map[idx]
                academic_year = admission_cycle.academic_year
                
                # Generate application number
                application_number = generate_application_number(
                    db=db,
                    institute_id=program_data.institute_id,
                    academic_year=academic_year
                )
                
                # Create application snapshot (from submitted data)
                snapshot = ApplicationSnapshot(
                    snapshot_created_at=datetime.utcnow(),
                    source_profile_id=existing_profile.id,
                    first_name=request.student_profile.first_name,
                    last_name=request.student_profile.last_name,
                    father_name=request.student_profile.father_name,
                    gender=request.student_profile.gender.value,
                    date_of_birth=request.student_profile.date_of_birth,
                    identity_doc_number=request.student_profile.identity_doc_number,
                    identity_doc_type=request.student_profile.identity_doc_type.value,
                    religion=request.student_profile.religion.value if request.student_profile.religion else None,
                    nationality=request.student_profile.nationality,
                    is_disabled=request.student_profile.is_disabled,
                    disability_details=request.student_profile.disability_details,
                    primary_email=request.student_profile.primary_email,
                    primary_phone=request.student_profile.primary_phone,
                    alternate_phone=request.student_profile.alternate_phone,
                    street_address=request.student_profile.street_address,
                    city=request.student_profile.city,
                    district=request.student_profile.district,
                    province=request.student_profile.province.value,
                    postal_code=request.student_profile.postal_code,
                    domicile_province=request.student_profile.domicile_province.value,
                    domicile_district=request.student_profile.domicile_district,
                    profile_picture_url=request.student_profile.profile_picture_url,
                    identity_doc_url=request.student_profile.identity_doc_url,
                )
                db.add(snapshot)
                db.flush()
                
                # Create guardian snapshot
                guardian_snapshot = ApplicationGuardianSnapshot(
                    application_snapshot_id=snapshot.id,
                    source_guardian_id=None,
                    guardian_relationship=request.guardian.guardian_relationship.value,
                    first_name=request.guardian.first_name,
                    last_name=request.guardian.last_name,
                    cnic=request.guardian.cnic,
                    phone_number=request.guardian.phone_number,
                    email=request.guardian.email,
                    occupation=request.guardian.occupation,
                    is_primary=request.guardian.is_primary,
                )
                db.add(guardian_snapshot)
                
                # Create academic snapshot
                academic_snapshot = ApplicationAcademicSnapshot(
                    application_snapshot_id=snapshot.id,
                    source_academic_id=None,
                    level=request.academic_record.level.value,
                    education_group=request.academic_record.education_group.value if request.academic_record.education_group else None,
                    institute_name=request.academic_record.institute_name,
                    board_name=request.academic_record.board_name,
                    roll_number=request.academic_record.roll_number,
                    year_of_passing=request.academic_record.year_of_passing,
                    total_marks=request.academic_record.total_marks,
                    obtained_marks=request.academic_record.obtained_marks,
                    grade=request.academic_record.grade,
                    result_card_url=request.academic_record.result_card_url,
                    is_verified=False,
                    verification_status=VerificationStatus.PENDING,
                )
                db.add(academic_snapshot)
                db.flush()
                
                # Create application
                application = Application(
                    application_number=application_number,
                    student_profile_id=existing_profile.id,
                    user_id=user.id,
                    application_snapshot_id=snapshot.id,
                    institute_id=program_data.institute_id,
                    preferred_campus_id=program_data.preferred_campus_id,
                    program_cycle_id=program_cycle.id,
                    quota_id=program_data.quota_id,
                    status=ApplicationStatus.SUBMITTED,
                    submitted_at=datetime.utcnow(),
                    workflow_instance_id=None,  # Will be set if workflow exists
                )
                db.add(application)
                db.flush()
                
                # Create status history
                status_history = ApplicationStatusHistory(
                    application_id=application.id,
                    from_status=None,
                    to_status=ApplicationStatus.SUBMITTED,
                    notes="Application submitted by student",
                    changed_by=user.id,
                )
                db.add(status_history)
                
                # ==================== WORKFLOW INTEGRATION ====================
                # Check if there's an active workflow for this institute
                workflow_def = db.query(WorkflowDefinition).filter(
                    WorkflowDefinition.institute_id == program_data.institute_id,
                    WorkflowDefinition.published == True,
                    WorkflowDefinition.active == True,
                ).order_by(WorkflowDefinition.version.desc()).first()
                
                if workflow_def:
                    try:
                        # Build subprocess registry
                        subprocess_refs = workflow_def.subprocess_refs or []
                        subprocess_registry = {}
                        if subprocess_refs:
                            subprocess_registry = build_subprocess_registry(subprocess_refs, db)
                        
                        # Load BPMN spec
                        spec, subprocess_specs = load_spec_from_xml(
                            xml_string=workflow_def.bpmn_xml,
                            spec_name=workflow_def.process_id,
                            subprocess_registry=subprocess_registry if subprocess_registry else None,
                        )
                        
                        # Prepare workflow data with application details
                        workflow_data = {
                            "application_id": str(application.id),
                            "application_number": application_number,
                            "student_name": f"{request.student_profile.first_name} {request.student_profile.last_name}",
                            "student_email": request.student_profile.primary_email,
                            "program_id": str(program_data.program_id),
                            "campus_id": str(program_data.preferred_campus_id),
                            "quota_id": str(program_data.quota_id),
                            "obtained_marks": request.academic_record.obtained_marks,
                            "total_marks": request.academic_record.total_marks,
                            "academic_level": request.academic_record.level.value,
                        }
                        
                        # Create workflow instance
                        workflow = create_workflow_instance(
                            spec,
                            subprocess_specs=subprocess_specs if subprocess_specs else None,
                            data=workflow_data,
                        )
                        
                        # Create workflow instance record
                        wf_instance = WorkflowInstance(
                            institute_id=program_data.institute_id,
                            workflow_definition_id=workflow_def.id,
                            business_key=application_number,
                            definition=workflow_def.process_id,
                            state=dumps_wf(workflow),
                            status="running",
                        )
                        db.add(wf_instance)
                        db.flush()
                        
                        # Link workflow to application
                        application.workflow_instance_id = wf_instance.id
                        
                        # Run service tasks
                        should_persist, waiting_task_ids = run_service_tasks(
                            wf=workflow,
                            db=db,
                            wf_row=wf_instance,
                            user=user,
                            auto_persist=False,
                        )
                        
                        # Update workflow state
                        wf_instance.state = dumps_wf(workflow)
                        wf_instance.current_tasks = waiting_task_ids
                        
                        if workflow.is_completed():
                            wf_instance.status = "completed"
                            wf_instance.completed_at = datetime.utcnow()
                        
                    except Exception as wf_error:
                        # Log workflow error but don't fail the application
                        print(f"Warning: Workflow creation failed for application {application_number}: {str(wf_error)}")
                        # Application is still created, just without workflow
                
                application_numbers.append(application_number)
            
            # Commit transaction
            db.commit()
            
            # ==================== STEP 4: SEND NOTIFICATIONS ====================
            # TODO: Implement email sending
            # For now, just log the details
            if is_new_student and student_password:
                # Would send welcome email with credentials
                print(f"Welcome email would be sent to {user.email} with password: {student_password}")
                print(f"Applications created: {', '.join(application_numbers)}")
            else:
                # Would send confirmation email
                print(f"Confirmation email would be sent to {user.email}")
                print(f"Applications created: {', '.join(application_numbers)}")
            
            # ==================== STEP 5: RETURN RESPONSE ====================
            return ApplicationSubmitResponse(
                message=f"Application(s) submitted successfully. Check your email for application details and login credentials."
            )
    
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error submitting application: {str(e)}"
        )
