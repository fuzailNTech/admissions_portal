from fastapi import APIRouter
from app.routers.auth import auth_router
from app.routers.workflow_catalog import workflow_catalog_router

# Create API router with prefix
api_router = APIRouter(prefix="/api/v1")

# Include all routers
api_router.include_router(auth_router)
api_router.include_router(workflow_catalog_router)

