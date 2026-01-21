from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class ApplicationCreate(BaseModel):
    """Schema for creating a new application."""
    institute_id: UUID = Field(..., description="ID of the institute")
    business_key: Optional[str] = Field(None, description="Optional business key (e.g., application ID, email)")
    initial_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Initial workflow data (will be merged with dummy data if not provided)"
    )


class ApplicationResponse(BaseModel):
    """Schema for application/workflow instance response."""
    id: UUID
    institute_id: UUID
    workflow_definition_id: UUID
    business_key: Optional[str]
    definition: str
    status: str
    current_tasks: Optional[list]
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

