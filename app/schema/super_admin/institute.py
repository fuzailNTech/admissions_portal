from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
import re


class InstituteCreate(BaseModel):
    """Schema for creating a new institute."""
    name: str = Field(..., min_length=1, max_length=255, description="Name of the institute")
    slug: Optional[str] = Field(None, description="URL-friendly identifier (auto-generated if not provided)")
    active: bool = Field(default=True, description="Whether the institute is active")

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        """Validate slug format if provided."""
        if v is not None and not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        return v


class InstituteUpdate(BaseModel):
    """Schema for updating an institute."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Name of the institute")
    slug: Optional[str] = Field(None, description="URL-friendly identifier")
    active: Optional[bool] = Field(None, description="Whether the institute is active")

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        """Validate slug format if provided."""
        if v is not None and not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        return v


class InstituteResponse(BaseModel):
    """Schema for institute response."""
    id: UUID
    name: str
    slug: str
    active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

