from fastapi import APIRouter
from app.routers.super_admin.institute import institute_router
from app.routers.super_admin.workflow_definition import workflow_definition_router
from app.routers.super_admin.workflow_catalog import workflow_catalog_router

# Create admin router with prefix
super_admin_router = APIRouter(prefix="/super_admin")

# Include all admin routers
super_admin_router.include_router(institute_router)
super_admin_router.include_router(workflow_definition_router)
super_admin_router.include_router(workflow_catalog_router)

__all__ = ["super_admin_router"]
