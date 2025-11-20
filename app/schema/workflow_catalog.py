from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class SubworkflowCreate(BaseModel):
    """Schema for creating a new subworkflow."""
    subflow_key: str = Field(..., description="Unique key for the subworkflow, e.g., 'communication.send_email'")
    version: int = Field(default=1, description="Version number of the subworkflow")
    process_id: str = Field(..., description="BPMN process ID")
    bpmn_xml: str = Field(..., description="BPMN XML content for the subworkflow")
    description: Optional[str] = Field(None, description="Description of the subworkflow")
    published: bool = Field(default=False, description="Whether the subworkflow is published")


class SubworkflowUpdate(BaseModel):
    """Schema for updating a subworkflow."""
    process_id: Optional[str] = Field(None, description="BPMN process ID")
    bpmn_xml: Optional[str] = Field(None, description="BPMN XML content for the subworkflow")
    description: Optional[str] = Field(None, description="Description of the subworkflow")
    published: Optional[bool] = Field(None, description="Whether the subworkflow is published")


class SubworkflowResponse(BaseModel):
    """Schema for subworkflow response (without bpmn_xml for list endpoints)."""
    id: UUID
    subflow_key: str
    version: int
    process_id: str
    description: Optional[str]
    published: bool
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class SubworkflowDetailResponse(BaseModel):
    """Schema for subworkflow detail response (includes bpmn_xml)."""
    id: UUID
    subflow_key: str
    version: int
    process_id: str
    bpmn_xml: str
    description: Optional[str]
    published: bool
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

