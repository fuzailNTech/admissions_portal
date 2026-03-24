from fastapi import APIRouter
from app.routers.admin.auth import admin_auth_router
from app.routers.admin.admission import admission_router
from app.routers.admin.institute import institute_router
from app.routers.admin.application import application_router
from app.routers.admin.user import admin_user_router

# Create admin router with prefix
admin_router = APIRouter(prefix="/admin")

# Include all admin routers
admin_router.include_router(admin_auth_router)
admin_router.include_router(admission_router)
admin_router.include_router(institute_router)
admin_router.include_router(application_router)
admin_router.include_router(admin_user_router)

__all__ = ["admin_router"]
