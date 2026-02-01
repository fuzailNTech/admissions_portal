# Import models in dependency order
from app.database.models.institute import Institute, Campus, Program, CampusProgram
from app.database.models.auth import User, UserRole, VerificationToken
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

__all__ = [
    "Institute",
    "Campus",
    "Program",
    "CampusProgram",
    "User",
    "UserRole",
    "VerificationToken",
    "WorkflowCatalog",
    "WorkflowDefinition",
    "WorkflowInstance",
    "AdmissionCycle",
    "CampusAdmissionCycle",
    "ProgramAdmissionCycle",
    "ProgramQuota",
    "CustomFormField",
    "ProgramFormField",
]
