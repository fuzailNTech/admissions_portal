"""
Seed institutes with campuses, programs, and admission cycles from JSON data.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.bpm.compiler.compiler import compile_manifest_to_bpmn
from app.database.models.admission import (
    AcademicSession,
    AdmissionCycle,
    AdmissionCycleStatus,
    CampusAdmissionCycle,
    ProgramAdmissionCycle,
    ProgramQuota,
    QuotaStatus,
    QuotaType,
)
from app.database.models.auth import StaffProfile, StaffRoleType, User
from app.database.models.institute import (
    AssignmentMode,
    Campus,
    CampusProgram,
    CampusType,
    Institute,
    InstituteLevel,
    InstituteStatus,
    InstituteType,
    Program,
    ShiftType,
)
from app.database.models.workflow import WorkflowDefinition
from app.routers.super_admin.institute import (
    _create_catalog_lookup,
    _derive_process_id,
    _load_default_manifest,
    _unpublish_other_workflows,
)
from app.settings import BASE_DIR
from app.utils.auth import generate_strong_password, get_password_hash

SEED_DATA_PATH = os.path.join(BASE_DIR, "seed", "data", "institute_admissions.json")


def load_seed_data() -> Dict[str, Any]:
    """Load institute/admission seed dataset from JSON file."""
    if not os.path.exists(SEED_DATA_PATH):
        raise FileNotFoundError(f"Seed data file not found: {SEED_DATA_PATH}")

    with open(SEED_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def preview_institute_admissions_seed() -> Dict[str, Any]:
    """Return a summary of what will be seeded without writing to the database."""
    data = load_seed_data()
    institutes = data.get("institutes", [])

    preview = []
    for institute in institutes:
        campuses = institute.get("campuses", [])
        programs = institute.get("programs", [])
        cycles = institute.get("admission_cycles", [])

        program_offerings = 0
        for cycle in cycles:
            for campus_offering in cycle.get("campus_offerings", []):
                program_offerings += len(campus_offering.get("programs", []))

        admin = institute.get("admin")
        workflow = institute.get("workflow_definition")

        preview.append(
            {
                "key": institute.get("key"),
                "name": institute.get("name"),
                "institute_code": institute.get("institute_code"),
                "campus_count": len(campuses),
                "program_count": len(programs),
                "admission_cycle_count": len(cycles),
                "program_offering_count": program_offerings,
                "admin_email": admin.get("email") if admin else None,
                "workflow_name": workflow.get("workflow_name") if workflow else None,
            }
        )

    return {
        "seed_data_path": SEED_DATA_PATH,
        "institute_count": len(institutes),
        "institutes": preview,
    }


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _enum_value(enum_cls: type, value: str):
    return enum_cls(value)


def seed_institute_admissions(
    db: Session,
    *,
    created_by: Optional[UUID] = None,
    update_existing: bool = False,
) -> Dict[str, Any]:
    """
    Seed institutes, campuses, programs, campus-program links, admission cycles,
    campus cycles, program cycles, and quotas from the JSON dataset.

    Skips institutes that already exist (by institute_code) unless update_existing=True.
    When update_existing=True, only the institute record is updated; related entities
    are still skipped if the institute already exists.
    """
    data = load_seed_data()
    results: Dict[str, List[Dict[str, Any]]] = {
        "created": [],
        "updated": [],
        "skipped": [],
        "errors": [],
    }

    for institute_data in data.get("institutes", []):
        institute_code = institute_data["institute_code"]
        try:
            existing_institute = (
                db.query(Institute)
                .filter(Institute.institute_code == institute_code)
                .first()
            )

            if existing_institute:
                if update_existing:
                    _update_institute(existing_institute, institute_data)
                    existing_institute.created_by = created_by
                    db.commit()
                    db.refresh(existing_institute)
                    results["updated"].append(
                        {
                            "institute_code": institute_code,
                            "id": str(existing_institute.id),
                            "note": "Institute updated; related entities were not re-seeded",
                        }
                    )
                else:
                    results["skipped"].append(
                        {
                            "institute_code": institute_code,
                            "reason": "Institute already exists",
                        }
                    )
                continue

            institute = _create_institute(db, institute_data, created_by)
            program_map = _create_programs(db, institute, institute_data.get("programs", []))
            campus_map = _create_campuses(
                db, institute, institute_data.get("campuses", []), created_by
            )
            _link_campus_programs(
                db,
                institute_data.get("campuses", []),
                campus_map,
                program_map,
                created_by,
            )
            cycle_summary = _create_admission_cycles(
                db,
                institute,
                institute_data.get("admission_cycles", []),
                campus_map,
                program_map,
                created_by,
            )
            admin_summary = _seed_institute_admin(
                db,
                institute,
                institute_data.get("admin"),
                assigned_by=created_by,
            )
            workflow_summary = _seed_workflow_definition(
                db,
                institute,
                institute_data.get("workflow_definition"),
                created_by=created_by,
            )

            db.commit()

            created_entry: Dict[str, Any] = {
                "institute_code": institute_code,
                "id": str(institute.id),
                "campuses": len(campus_map),
                "programs": len(program_map),
                "admission_cycles": cycle_summary["cycles"],
                "program_offerings": cycle_summary["program_offerings"],
                "quotas": cycle_summary["quotas"],
            }
            if admin_summary:
                created_entry["admin"] = admin_summary
            if workflow_summary:
                created_entry["workflow_definition"] = workflow_summary
            results["created"].append(created_entry)
        except Exception as exc:
            db.rollback()
            results["errors"].append(
                {
                    "institute_code": institute_code,
                    "error": str(exc),
                }
            )

    return {
        "message": "Institute and admissions seeding completed",
        "seed_data_path": SEED_DATA_PATH,
        "created_count": len(results["created"]),
        "updated_count": len(results["updated"]),
        "skipped_count": len(results["skipped"]),
        "error_count": len(results["errors"]),
        "details": results,
    }


def _update_institute(institute: Institute, data: Dict[str, Any]) -> None:
    institute.name = data["name"]
    institute.institute_type = _enum_value(InstituteType, data["institute_type"])
    institute.institute_level = _enum_value(InstituteLevel, data["institute_level"])
    institute.status = _enum_value(InstituteStatus, data.get("status", "active"))
    institute.application_assignment_mode = _enum_value(
        AssignmentMode, data.get("application_assignment_mode", "auto")
    )
    institute.registration_number = data.get("registration_number")
    institute.regulatory_body = data.get("regulatory_body")
    institute.established_year = data.get("established_year")
    institute.primary_email = data.get("primary_email")
    institute.primary_phone = data.get("primary_phone")
    institute.website_url = data.get("website_url")
    institute.custom_metadata = data.get("custom_metadata", {})


def _create_institute(
    db: Session, data: Dict[str, Any], created_by: Optional[UUID]
) -> Institute:
    institute = Institute(
        name=data["name"],
        institute_code=data["institute_code"],
        institute_type=_enum_value(InstituteType, data["institute_type"]),
        institute_level=_enum_value(InstituteLevel, data["institute_level"]),
        status=_enum_value(InstituteStatus, data.get("status", "active")),
        application_assignment_mode=_enum_value(
            AssignmentMode, data.get("application_assignment_mode", "auto")
        ),
        registration_number=data.get("registration_number"),
        regulatory_body=data.get("regulatory_body"),
        established_year=data.get("established_year"),
        primary_email=data.get("primary_email"),
        primary_phone=data.get("primary_phone"),
        website_url=data.get("website_url"),
        custom_metadata=data.get("custom_metadata", {}),
        created_by=created_by,
    )
    db.add(institute)
    db.flush()
    return institute


def _create_programs(
    db: Session, institute: Institute, programs: List[Dict[str, Any]]
) -> Dict[str, Program]:
    program_map: Dict[str, Program] = {}
    for program_data in programs:
        program = Program(
            institute_id=institute.id,
            name=program_data["name"],
            code=program_data["code"],
            level=program_data["level"],
            category=program_data.get("category"),
            duration_years=program_data.get("duration_years"),
            fee=Decimal(program_data["fee"]) if program_data.get("fee") else None,
            shift=_enum_value(ShiftType, program_data.get("shift", "morning")),
            description=program_data.get("description"),
            custom_metadata=program_data.get("custom_metadata", {}),
            is_active=program_data.get("is_active", True),
        )
        db.add(program)
        db.flush()
        program_map[program.code] = program
    return program_map


def _create_campuses(
    db: Session,
    institute: Institute,
    campuses: List[Dict[str, Any]],
    created_by: Optional[UUID],
) -> Dict[str, Campus]:
    campus_map: Dict[str, Campus] = {}
    for campus_data in campuses:
        campus = Campus(
            institute_id=institute.id,
            name=campus_data["name"],
            campus_code=campus_data.get("campus_code"),
            campus_type=_enum_value(CampusType, campus_data["campus_type"]),
            country=campus_data.get("country", "Pakistan"),
            province_state=campus_data.get("province_state"),
            city=campus_data.get("city"),
            postal_code=campus_data.get("postal_code"),
            address_line=campus_data.get("address_line"),
            campus_email=campus_data.get("campus_email"),
            campus_phone=campus_data.get("campus_phone"),
            timezone=campus_data.get("timezone", "Asia/Karachi"),
            custom_metadata=campus_data.get("custom_metadata", {}),
            is_active=campus_data.get("is_active", True),
            created_by=created_by,
        )
        db.add(campus)
        db.flush()
        campus_map[campus_data["key"]] = campus
    return campus_map


def _link_campus_programs(
    db: Session,
    campuses: List[Dict[str, Any]],
    campus_map: Dict[str, Campus],
    program_map: Dict[str, Program],
    created_by: Optional[UUID],
) -> None:
    for campus_data in campuses:
        campus = campus_map[campus_data["key"]]
        for program_code in campus_data.get("program_codes", []):
            program = program_map.get(program_code)
            if program is None:
                raise ValueError(
                    f"Campus '{campus_data['key']}' references unknown program '{program_code}'"
                )
            db.add(
                CampusProgram(
                    campus_id=campus.id,
                    program_id=program.id,
                    is_active=True,
                    created_by=created_by,
                )
            )
    db.flush()


def _create_admission_cycles(
    db: Session,
    institute: Institute,
    cycles: List[Dict[str, Any]],
    campus_map: Dict[str, Campus],
    program_map: Dict[str, Program],
    created_by: Optional[UUID],
) -> Dict[str, int]:
    summary = {"cycles": 0, "program_offerings": 0, "quotas": 0}

    for cycle_data in cycles:
        cycle = AdmissionCycle(
            institute_id=institute.id,
            name=cycle_data["name"],
            academic_year=cycle_data["academic_year"],
            session=_enum_value(AcademicSession, cycle_data.get("session", "annual")),
            status=_enum_value(
                AdmissionCycleStatus, cycle_data.get("status", "draft")
            ),
            application_start_date=_parse_datetime(cycle_data["application_start_date"]),
            application_end_date=_parse_datetime(cycle_data["application_end_date"]),
            description=cycle_data.get("description"),
            custom_metadata=cycle_data.get("custom_metadata", {}),
            is_published=cycle_data.get("is_published", False),
            created_by=created_by,
        )
        db.add(cycle)
        db.flush()
        summary["cycles"] += 1

        for campus_offering in cycle_data.get("campus_offerings", []):
            campus = campus_map.get(campus_offering["campus_key"])
            if campus is None:
                raise ValueError(
                    f"Admission cycle references unknown campus '{campus_offering['campus_key']}'"
                )

            campus_cycle = CampusAdmissionCycle(
                campus_id=campus.id,
                admission_cycle_id=cycle.id,
                is_open=campus_offering.get("is_open", True),
                closure_reason=campus_offering.get("closure_reason"),
                custom_metadata=campus_offering.get("custom_metadata", {}),
                created_by=created_by,
            )
            db.add(campus_cycle)
            db.flush()

            for program_offering in campus_offering.get("programs", []):
                program = program_map.get(program_offering["program_code"])
                if program is None:
                    raise ValueError(
                        "Admission cycle references unknown program "
                        f"'{program_offering['program_code']}'"
                    )

                program_cycle = ProgramAdmissionCycle(
                    campus_admission_cycle_id=campus_cycle.id,
                    program_id=program.id,
                    total_seats=program_offering["total_seats"],
                    description=program_offering.get("description"),
                    custom_metadata=program_offering.get("custom_metadata", {}),
                    is_active=program_offering.get("is_active", True),
                )
                db.add(program_cycle)
                db.flush()
                summary["program_offerings"] += 1

                for quota_data in program_offering.get("quotas", []):
                    db.add(
                        ProgramQuota(
                            program_cycle_id=program_cycle.id,
                            quota_type=_enum_value(QuotaType, quota_data["quota_type"]),
                            quota_name=quota_data["quota_name"],
                            allocated_seats=quota_data["allocated_seats"],
                            eligibility_requirements=quota_data.get(
                                "eligibility_requirements", {}
                            ),
                            required_documents=quota_data.get("required_documents", []),
                            minimum_marks=quota_data.get("minimum_marks"),
                            priority_order=quota_data.get("priority_order", 0),
                            status=_enum_value(
                                QuotaStatus, quota_data.get("status", "active")
                            ),
                            description=quota_data.get("description"),
                            custom_metadata=quota_data.get("custom_metadata", {}),
                        )
                    )
                    summary["quotas"] += 1

    db.flush()
    return summary


def _seed_institute_admin(
    db: Session,
    institute: Institute,
    admin_data: Optional[Dict[str, Any]],
    *,
    assigned_by: Optional[UUID],
) -> Optional[Dict[str, Any]]:
    """Create a user (if needed) and assign them as institute admin."""
    if not admin_data:
        return None

    email = admin_data["email"].strip().lower()
    first_name = admin_data["first_name"]
    last_name = admin_data["last_name"]

    user = db.query(User).filter(User.email == email).first()
    generated_password: Optional[str] = None

    if user is None:
        generated_password = admin_data.get("password") or generate_strong_password()
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password_hash=get_password_hash(generated_password),
            is_temporary_password=True,
            verified=True,
            is_super_admin=False,
            is_active=True,
        )
        db.add(user)
        db.flush()
        user_created = True
    else:
        if not user.first_name:
            user.first_name = first_name
        if not user.last_name:
            user.last_name = last_name
        if not user.is_active:
            raise ValueError(f"Cannot assign inactive user '{email}' as institute admin")
        user_created = False

    if not user.first_name or not user.last_name:
        raise ValueError(
            f"User '{email}' must have first_name and last_name before institute admin assignment"
        )

    existing_profile = (
        db.query(StaffProfile).filter(StaffProfile.user_id == user.id).first()
    )
    if existing_profile:
        if existing_profile.institute_id == institute.id:
            summary = {
                "user_id": str(user.id),
                "email": user.email,
                "staff_profile_id": str(existing_profile.id),
                "user_created": user_created,
                "already_assigned": True,
            }
            if generated_password:
                summary["password"] = generated_password
            return summary
        raise ValueError(
            f"User '{email}' already has a staff profile at another institute"
        )

    staff_profile = StaffProfile(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=admin_data.get("phone_number"),
        role=StaffRoleType.INSTITUTE_ADMIN,
        institute_id=institute.id,
        is_active=True,
        assigned_by=assigned_by,
    )
    db.add(staff_profile)
    db.flush()

    summary = {
        "user_id": str(user.id),
        "email": user.email,
        "staff_profile_id": str(staff_profile.id),
        "user_created": user_created,
        "already_assigned": False,
    }
    if generated_password:
        summary["password"] = generated_password
    return summary


def _seed_workflow_definition(
    db: Session,
    institute: Institute,
    workflow_data: Optional[Dict[str, Any]],
    *,
    created_by: Optional[UUID],
) -> Optional[Dict[str, Any]]:
    """Create a workflow definition for the institute using the default manifest."""
    if not workflow_data:
        return None

    workflow_name = workflow_data["workflow_name"].strip()
    version = workflow_data.get("version", 1)
    published = workflow_data.get("published", False)
    active = workflow_data.get("active", True)
    process_id = _derive_process_id(workflow_name)

    existing = (
        db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.institute_id == institute.id,
            WorkflowDefinition.process_id == process_id,
            WorkflowDefinition.version == version,
        )
        .first()
    )
    if existing:
        return {
            "workflow_definition_id": str(existing.id),
            "process_id": existing.process_id,
            "workflow_name": existing.workflow_name,
            "version": existing.version,
            "published": existing.published,
            "already_exists": True,
        }

    manifest_json = _load_default_manifest().copy()
    manifest_json["workflow_name"] = workflow_name
    manifest_json["process_id"] = process_id

    catalog_lookup = _create_catalog_lookup(db)
    bpmn_xml, subprocess_refs = compile_manifest_to_bpmn(
        manifest_json, catalog_lookup=catalog_lookup
    )

    if published:
        _unpublish_other_workflows(db, institute.id)

    workflow_definition = WorkflowDefinition(
        institute_id=institute.id,
        process_id=process_id,
        workflow_name=workflow_name,
        version=version,
        manifest_json=manifest_json,
        bpmn_xml=bpmn_xml,
        subprocess_refs=subprocess_refs,
        published=published,
        active=active,
        created_by=created_by,
    )
    if published:
        workflow_definition.published_at = datetime.utcnow()

    db.add(workflow_definition)
    db.flush()

    return {
        "workflow_definition_id": str(workflow_definition.id),
        "process_id": workflow_definition.process_id,
        "workflow_name": workflow_definition.workflow_name,
        "version": workflow_definition.version,
        "published": workflow_definition.published,
        "already_exists": False,
    }
