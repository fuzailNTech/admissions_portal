from fastapi import APIRouter
from app.routers.student.auth import student_auth_router
from app.routers.student.institutes import institute_router
from app.routers.student.application import application_router

# Create student router with prefix
student_router = APIRouter(prefix="/student")

# Include all student routers
student_router.include_router(student_auth_router)
student_router.include_router(institute_router)
student_router.include_router(application_router)

__all__ = ["student_router"]
