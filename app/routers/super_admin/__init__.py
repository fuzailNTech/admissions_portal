from fastapi import APIRouter
from app.routers.super_admin.auth import super_admin_auth_router
from app.routers.super_admin.institute import institute_router
from app.routers.super_admin.dummy import dummy_router
from app.routers.super_admin.seed import seed_router
from app.routers.super_admin.workflow_definition import workflow_definition_router
from app.routers.super_admin.workflow_catalog import workflow_catalog_router

# Create super admin router with prefix
super_admin_router = APIRouter(prefix="/super-admin")

# Include all super admin routers
super_admin_router.include_router(super_admin_auth_router)
super_admin_router.include_router(institute_router)
super_admin_router.include_router(dummy_router)
super_admin_router.include_router(seed_router)
super_admin_router.include_router(workflow_definition_router)
super_admin_router.include_router(workflow_catalog_router)

__all__ = ["super_admin_router"]
