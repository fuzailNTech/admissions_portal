# Import models in dependency order
from app.database.models.institute import Institute, Campus, Program
from app.database.models.auth import User, UserRole, VerificationToken
from app.database.models.workflow import (
    WorkflowCatalog,
    WorkflowDefinition,
    WorkflowInstance,
)
from app.database.models.admission import (
    AdmissionCycle,
    ProgramAdmissionCycle,
    ProgramQuota,
    CustomFormField,
    ProgramFormField,
)

__all__ = [
    "Institute",
    "Campus",
    "User",
    "UserRole",
    "VerificationToken",
    "WorkflowCatalog",
    "WorkflowDefinition",
    "WorkflowInstance",
    "Program",
    "AdmissionCycle",
    "ProgramAdmissionCycle",
    "ProgramQuota",
    "CustomFormField",
    "ProgramFormField",
]
