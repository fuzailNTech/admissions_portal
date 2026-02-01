from fastapi import APIRouter
from app.routers.admin import admin_router
from app.routers.student import student_router
from app.routers.super_admin import super_admin_router

# Create API router with prefix
api_router = APIRouter(prefix="/api/v1")

# Include all routers (organized by user role)
api_router.include_router(admin_router)
api_router.include_router(student_router)
api_router.include_router(super_admin_router)
