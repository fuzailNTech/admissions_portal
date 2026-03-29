"""Admin schemas for campus visit slots."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.database.models.campus_visit import (
    CampusVisitBookingStatus,
    CampusVisitSlotStatus,
)


class CampusVisitSlotCreate(BaseModel):
    campus_id: UUID
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(..., ge=1)
    status: CampusVisitSlotStatus = CampusVisitSlotStatus.DRAFT
    title: Optional[str] = None
    notes: Optional[str] = None


class CampusVisitSlotUpdate(BaseModel):
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    capacity: Optional[int] = Field(None, ge=1)
    status: Optional[CampusVisitSlotStatus] = None
    title: Optional[str] = None
    notes: Optional[str] = None


class CampusVisitSlotResponse(BaseModel):
    id: UUID
    campus_id: UUID
    starts_at: datetime
    ends_at: datetime
    capacity: int
    status: CampusVisitSlotStatus
    title: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    filled: int = Field(..., ge=0, description="Bookings counting toward capacity (excludes cancelled)")
    remaining: int = Field(..., ge=0, description="capacity - filled")

    class Config:
        from_attributes = True


class PaginatedCampusVisitSlotListResponse(BaseModel):
    items: List[CampusVisitSlotResponse] = Field(..., description="Page of visit slots")
    total: int = Field(..., ge=0, description="Total items matching filters")


class CampusVisitSlotSummary(BaseModel):
    """Slot metadata embedded in booking list/detail responses."""

    id: UUID
    campus_id: UUID
    starts_at: datetime
    ends_at: datetime
    title: Optional[str] = None
    status: CampusVisitSlotStatus
    capacity: int = Field(..., ge=1)

    class Config:
        from_attributes = True


class CampusVisitBookingUpdate(BaseModel):
    status: Optional[CampusVisitBookingStatus] = None
    remarks: Optional[str] = None


class CampusVisitBookingListItem(BaseModel):
    id: UUID
    slot_id: UUID
    user_id: Optional[UUID] = None
    visitor_name: str
    visitor_email: str
    visitor_phone: str
    status: CampusVisitBookingStatus
    remarks: Optional[str] = None
    visited_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    slot: CampusVisitSlotSummary


class PaginatedCampusVisitBookingListResponse(BaseModel):
    items: List[CampusVisitBookingListItem] = Field(..., description="Page of visit bookings")
    total: int = Field(..., ge=0, description="Total items matching filters")
