from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


class WorkflowDefinitionCreate(BaseModel):
    """Schema for creating a new workflow definition. Uses default manifest; only workflow_name is required."""
    workflow_name: str = Field(..., min_length=1, max_length=255, description="Human-readable workflow name")
    version: int = Field(default=1, ge=1, description="Version number of the workflow")
    published: bool = Field(default=False, description="Whether the workflow is published")
    active: bool = Field(default=True, description="Whether the workflow is active")

    # @field_validator('manifest_json')
    # @classmethod
    # def validate_manifest(cls, v: Dict[str, Any]) -> Dict[str, Any]:
    #     """Validate manifest structure."""
    #     required_fields = ['start', 'nodes']
    #     for field in required_fields:
    #         if field not in v:
    #             raise ValueError(f"Manifest must contain '{field}' field")
    #     return v


class WorkflowDefinitionUpdate(BaseModel):
    """Schema for updating a workflow definition."""
    workflow_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Human-readable workflow name")
    manifest_json: Optional[Dict[str, Any]] = Field(None, description="Workflow manifest JSON")
    published: Optional[bool] = Field(None, description="Whether the workflow is published")
    active: Optional[bool] = Field(None, description="Whether the workflow is active")

    @field_validator('manifest_json')
    @classmethod
    def validate_manifest(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate manifest structure if provided."""
        if v is not None:
            required_fields = ['start', 'nodes']
            for field in required_fields:
                if field not in v:
                    raise ValueError(f"Manifest must contain '{field}' field")
        return v


class WorkflowDefinitionResponse(BaseModel):
    """Schema for workflow definition response (without bpmn_xml for list endpoints)."""
    id: UUID
    institute_id: UUID
    process_id: str
    workflow_name: str
    version: int
    subprocess_refs: Optional[List[Dict[str, Any]]]
    published: bool
    active: bool
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]
    published_at: Optional[datetime]

    class Config:
        from_attributes = True


class WorkflowDefinitionDetailResponse(BaseModel):
    """Schema for workflow definition detail response (includes bpmn_xml and manifest_json)."""
    id: UUID
    institute_id: UUID
    process_id: str
    workflow_name: str
    version: int
    manifest_json: Dict[str, Any]
    bpmn_xml: str
    subprocess_refs: Optional[List[Dict[str, Any]]]
    published: bool
    active: bool
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]
    published_at: Optional[datetime]

    class Config:
        from_attributes = True

