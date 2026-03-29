"""Student-facing schemas for campus visit browsing."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.database.models.campus_visit import CampusVisitBookingStatus
from app.database.models.institute import CampusType


class CampusVisitSlotPublic(BaseModel):
    """A bookable visit window (public fields only)."""

    id: UUID
    starts_at: datetime
    ends_at: datetime
    title: Optional[str] = None
    remaining: int = Field(..., ge=0, description="Seats still available for this slot")


class CampusWithVisitSlots(BaseModel):
    id: UUID
    name: str
    campus_type: CampusType
    city: Optional[str] = None
    slots: List[CampusVisitSlotPublic] = Field(default_factory=list)


class InstituteCampusVisitSlotsResponse(BaseModel):
    institute_id: UUID
    institute_name: str
    campuses: List[CampusWithVisitSlots]


class CampusVisitBookRequest(BaseModel):
    slot_id: UUID
    visitor_name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    phone: str = Field(..., min_length=1, max_length=30)


class CampusVisitBookResponse(BaseModel):
    id: UUID
    slot_id: UUID
    visitor_name: str
    visitor_email: str
    visitor_phone: str
    status: CampusVisitBookingStatus
    created_at: datetime
    slot: CampusVisitSlotPublic
