"""Admin CRUD for campus visit slots (institute + campus admins)."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database.config.db import get_db
from app.database.models.campus_visit import (
    CampusVisitBooking,
    CampusVisitBookingStatus,
    CampusVisitSlot,
    CampusVisitSlotStatus,
)
from app.database.models.institute import Campus
from app.database.models.auth import StaffProfile
from app.schema.admin.campus_visit import (
    CampusVisitBookingListItem,
    CampusVisitBookingUpdate,
    CampusVisitSlotCreate,
    CampusVisitSlotResponse,
    CampusVisitSlotSummary,
    CampusVisitSlotUpdate,
    PaginatedCampusVisitBookingListResponse,
    PaginatedCampusVisitSlotListResponse,
)
from app.utils.auth import can_access_campus, get_accessible_campuses, require_admin_staff

campus_visit_router = APIRouter(prefix="/campus-visits", tags=["Admin - Campus visits"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _validate_list_date_range(
    starts_at: Optional[datetime],
    ends_at: Optional[datetime],
) -> None:
    if starts_at is not None and ends_at is not None:
        range_start = _ensure_aware_utc(starts_at)
        range_end = _ensure_aware_utc(ends_at)
        if range_start > range_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="starts_at must be on or before ends_at",
            )


def _validate_slot_window_future(starts_at: datetime, ends_at: datetime) -> None:
    starts_at = _ensure_aware_utc(starts_at)
    ends_at = _ensure_aware_utc(ends_at)
    now = _utc_now()
    if starts_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visit slot must start in the future",
        )
    if ends_at <= starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ends_at must be after starts_at",
        )


def _slot_to_summary(slot: CampusVisitSlot) -> CampusVisitSlotSummary:
    return CampusVisitSlotSummary(
        id=slot.id,
        campus_id=slot.campus_id,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        title=slot.title,
        status=slot.status,
        capacity=slot.capacity,
    )


def _booking_to_list_item(booking: CampusVisitBooking) -> CampusVisitBookingListItem:
    return CampusVisitBookingListItem(
        id=booking.id,
        slot_id=booking.slot_id,
        user_id=booking.user_id,
        visitor_name=booking.visitor_name,
        visitor_email=booking.visitor_email,
        visitor_phone=booking.visitor_phone,
        status=booking.status,
        remarks=booking.remarks,
        visited_at=booking.visited_at,
        cancelled_at=booking.cancelled_at,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
        slot=_slot_to_summary(booking.slot),
    )


def _slot_to_response(slot: CampusVisitSlot, filled: int) -> CampusVisitSlotResponse:
    remaining = max(0, slot.capacity - filled)
    return CampusVisitSlotResponse(
        id=slot.id,
        campus_id=slot.campus_id,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        capacity=slot.capacity,
        status=slot.status,
        title=slot.title,
        notes=slot.notes,
        created_at=slot.created_at,
        updated_at=slot.updated_at,
        created_by=slot.created_by,
        filled=filled,
        remaining=remaining,
    )


def _get_booking_for_staff(
    db: Session,
    booking_id: UUID,
    staff: StaffProfile,
) -> CampusVisitBooking:
    booking = (
        db.query(CampusVisitBooking)
        .options(joinedload(CampusVisitBooking.slot))
        .filter(CampusVisitBooking.id == booking_id)
        .first()
    )
    if not booking or booking.slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit booking not found")
    if not can_access_campus(booking.slot.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this visit booking",
        )
    return booking


def _get_slot_for_staff(
    db: Session,
    slot_id: UUID,
    staff: StaffProfile,
) -> CampusVisitSlot:
    slot = db.query(CampusVisitSlot).filter(CampusVisitSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit slot not found")
    if not can_access_campus(slot.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this visit slot",
        )
    return slot


@campus_visit_router.post(
    "/slots",
    response_model=CampusVisitSlotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a campus visit slot",
)
def create_campus_visit_slot(
    body: CampusVisitSlotCreate,
    staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    if not can_access_campus(body.campus_id, staff, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this campus",
        )
    _validate_slot_window_future(body.starts_at, body.ends_at)

    slot = CampusVisitSlot(
        campus_id=body.campus_id,
        starts_at=_ensure_aware_utc(body.starts_at),
        ends_at=_ensure_aware_utc(body.ends_at),
        capacity=body.capacity,
        status=body.status,
        title=body.title,
        notes=body.notes,
        created_by=staff.user_id,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return _slot_to_response(slot, 0)


@campus_visit_router.get(
    "/slots",
    response_model=PaginatedCampusVisitSlotListResponse,
    summary="List campus visit slots",
)
def list_campus_visit_slots(
    staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
    campus_id: Optional[UUID] = Query(None, description="Filter by campus"),
    status: Optional[CampusVisitSlotStatus] = Query(None, description="Filter by slot status"),
    starts_at: Optional[datetime] = Query(
        None,
        description="Range start (inclusive): only slots whose starts_at is on or after this",
    ),
    ends_at: Optional[datetime] = Query(
        None,
        description="Range end (inclusive): only slots whose starts_at is on or before this",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    accessible_ids = [c.id for c in get_accessible_campuses(staff, db)]
    if not accessible_ids:
        return PaginatedCampusVisitSlotListResponse(items=[], total=0)

    _validate_list_date_range(starts_at, ends_at)

    query = (
        db.query(CampusVisitSlot)
        .join(Campus, Campus.id == CampusVisitSlot.campus_id)
        .filter(Campus.institute_id == staff.institute_id)
    )

    if campus_id is not None:
        if campus_id not in accessible_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this campus",
            )
        query = query.filter(CampusVisitSlot.campus_id == campus_id)
    else:
        query = query.filter(CampusVisitSlot.campus_id.in_(accessible_ids))

    if status is not None:
        query = query.filter(CampusVisitSlot.status == status)
    if starts_at is not None:
        query = query.filter(CampusVisitSlot.starts_at >= _ensure_aware_utc(starts_at))
    if ends_at is not None:
        query = query.filter(CampusVisitSlot.starts_at <= _ensure_aware_utc(ends_at))

    query = query.order_by(CampusVisitSlot.starts_at.asc())
    total = query.count()
    slots = query.offset(skip).limit(limit).all()

    items = [_slot_to_response(s, s.filled(db)) for s in slots]
    return PaginatedCampusVisitSlotListResponse(items=items, total=total)




@campus_visit_router.get(
    "/slots/{slot_id}",
    response_model=CampusVisitSlotResponse,
    summary="Get a campus visit slot by ID",
)
def get_campus_visit_slot(
    slot_id: UUID,
    staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    slot = _get_slot_for_staff(db, slot_id, staff)
    filled = slot.filled(db)
    return _slot_to_response(slot, filled)


@campus_visit_router.patch(
    "/slots/{slot_id}",
    response_model=CampusVisitSlotResponse,
    summary="Update a campus visit slot",
)
def update_campus_visit_slot(
    slot_id: UUID,
    body: CampusVisitSlotUpdate,
    staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    slot = _get_slot_for_staff(db, slot_id, staff)

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        filled = slot.filled(db)
        return _slot_to_response(slot, filled)

    new_starts = (
        _ensure_aware_utc(update_data["starts_at"])
        if "starts_at" in update_data
        else _ensure_aware_utc(slot.starts_at)
    )
    new_ends = (
        _ensure_aware_utc(update_data["ends_at"])
        if "ends_at" in update_data
        else _ensure_aware_utc(slot.ends_at)
    )

    if "starts_at" in update_data or "ends_at" in update_data:
        if "starts_at" in update_data:
            if new_starts <= _utc_now():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Visit slot must start in the future",
                )
        if new_ends <= new_starts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ends_at must be after starts_at",
            )

    if "capacity" in update_data:
        filled = slot.filled(db)
        if update_data["capacity"] < filled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="capacity cannot be less than current filled count",
            )

    for key, value in update_data.items():
        if key in ("starts_at", "ends_at"):
            value = _ensure_aware_utc(value)
        setattr(slot, key, value)

    db.commit()
    db.refresh(slot)
    filled = slot.filled(db)
    return _slot_to_response(slot, filled)


@campus_visit_router.delete(
    "/slots/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a campus visit slot",
)
def delete_campus_visit_slot(
    slot_id: UUID,
    staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    slot = _get_slot_for_staff(db, slot_id, staff)
    has_booking = (
        db.query(CampusVisitBooking)
        .filter(CampusVisitBooking.slot_id == slot.id)
        .first()
    )
    if has_booking is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete slot while bookings exist for it",
        )
    db.delete(slot)
    db.commit()
    return None





@campus_visit_router.get(
    "/bookings",
    response_model=PaginatedCampusVisitBookingListResponse,
    summary="List campus visit bookings",
)
def list_campus_visit_bookings(
    staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
    campus_id: Optional[UUID] = Query(None, description="Filter by campus (slot's campus)"),
    status: Optional[CampusVisitBookingStatus] = Query(None, description="Filter by booking status"),
    starts_at: Optional[datetime] = Query(
        None,
        description="Range start (inclusive): only bookings whose slot starts_at is on or after this",
    ),
    ends_at: Optional[datetime] = Query(
        None,
        description="Range end (inclusive): only bookings whose slot starts_at is on or before this",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    accessible_ids = [c.id for c in get_accessible_campuses(staff, db)]
    if not accessible_ids:
        return PaginatedCampusVisitBookingListResponse(items=[], total=0)

    _validate_list_date_range(starts_at, ends_at)

    query = (
        db.query(CampusVisitBooking)
        .options(joinedload(CampusVisitBooking.slot))
        .join(CampusVisitSlot, CampusVisitSlot.id == CampusVisitBooking.slot_id)
        .join(Campus, Campus.id == CampusVisitSlot.campus_id)
        .filter(Campus.institute_id == staff.institute_id)
    )

    if campus_id is not None:
        if campus_id not in accessible_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this campus",
            )
        query = query.filter(CampusVisitSlot.campus_id == campus_id)
    else:
        query = query.filter(CampusVisitSlot.campus_id.in_(accessible_ids))

    if status is not None:
        query = query.filter(CampusVisitBooking.status == status)
    if starts_at is not None:
        query = query.filter(CampusVisitSlot.starts_at >= _ensure_aware_utc(starts_at))
    if ends_at is not None:
        query = query.filter(CampusVisitSlot.starts_at <= _ensure_aware_utc(ends_at))

    query = query.order_by(CampusVisitSlot.starts_at.asc(), CampusVisitBooking.created_at.desc())
    total = query.count()
    bookings = query.offset(skip).limit(limit).all()

    items = [_booking_to_list_item(b) for b in bookings]
    return PaginatedCampusVisitBookingListResponse(items=items, total=total)


@campus_visit_router.patch(
    "/bookings/{booking_id}",
    response_model=CampusVisitBookingListItem,
    summary="Update a campus visit booking (status, remarks)",
)
def update_campus_visit_booking(
    booking_id: UUID,
    body: CampusVisitBookingUpdate,
    staff: StaffProfile = Depends(require_admin_staff),
    db: Session = Depends(get_db),
):
    booking = _get_booking_for_staff(db, booking_id, staff)
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return _booking_to_list_item(booking)

    if "status" in update_data:
        new_status = update_data["status"]
        booking.status = new_status
        now = _utc_now()
        if new_status == CampusVisitBookingStatus.VISITED:
            booking.visited_at = now
        elif new_status == CampusVisitBookingStatus.CANCELLED:
            booking.cancelled_at = now
        elif new_status == CampusVisitBookingStatus.BOOKED:
            booking.cancelled_at = None
            booking.visited_at = None

    if "remarks" in update_data:
        booking.remarks = update_data["remarks"]

    db.commit()
    db.refresh(booking)
    return _booking_to_list_item(booking)