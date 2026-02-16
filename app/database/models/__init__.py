# Import models in dependency order
from app.database.models.institute import Institute, Campus, Program, CampusProgram
from app.database.models.auth import User, StaffProfile, StaffCampus, StaffRoleType
from app.database.models.student import (
    StudentProfile,
    StudentGuardian,
    StudentAcademicRecord,
    GenderType,
    IdentityDocumentType,
    ReligionType,
    ProvinceType,
    GuardianRelationship,
    AcademicLevel,
    EducationGroup,
)
from app.database.models.workflow import (
    WorkflowCatalog,
    WorkflowDefinition,
    WorkflowInstance,
)
from app.database.models.admission import (
    AdmissionCycle,
    CampusAdmissionCycle,
    ProgramAdmissionCycle,
    ProgramQuota,
    CustomFormField,
    ProgramFormField,
)
from app.database.models.application import (
    Application,
    ApplicationSnapshot,
    ApplicationGuardianSnapshot,
    ApplicationAcademicSnapshot,
    ApplicationDocument,
    ApplicationComment,
    StudentComment,
    ApplicationStatusHistory,
    ApplicationNumberSequence
)

__all__ = [
    "Institute",
    "Campus",
    "Program",
    "CampusProgram",
    "User",
    "StaffProfile",
    "StaffCampus",
    "StaffRoleType",
    "StudentProfile",
    "StudentGuardian",
    "StudentAcademicRecord",
    "GenderType",
    "IdentityDocumentType",
    "ReligionType",
    "ProvinceType",
    "GuardianRelationship",
    "AcademicLevel",
    "EducationGroup",
    "WorkflowCatalog",
    "WorkflowDefinition",
    "WorkflowInstance",
    "AdmissionCycle",
    "CampusAdmissionCycle",
    "ProgramAdmissionCycle",
    "ProgramQuota",
    "CustomFormField",
    "ProgramFormField",
    "Application",
    "ApplicationSnapshot",
    "ApplicationGuardianSnapshot",
    "ApplicationAcademicSnapshot",
    "ApplicationDocument",
    "ApplicationComment",
    "StudentComment",
    "ApplicationStatusHistory",
    "ApplicationNumberSequence",
]
