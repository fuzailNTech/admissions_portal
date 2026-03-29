import uuid
import enum
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Text,
    ForeignKey,
    Enum as SQLEnum,
    Index,
    UniqueConstraint,
    CheckConstraint,
    select,
    func as sqla_func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, relationship
from sqlalchemy.sql import func

from app.database.config.db import Base


class CampusVisitSlotStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    PAUSED = "paused"
    CLOSED = "closed"


class CampusVisitBookingStatus(str, enum.Enum):
    BOOKED = "booked"
    VISITED = "visited"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class CampusVisitSlot(Base):
    """Time-bounded visit capacity window for a campus."""

    __tablename__ = "campus_visit_slots"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    campus_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campuses.id", ondelete="CASCADE"),
        nullable=False,
    )
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    capacity = Column(Integer, nullable=False)
    status = Column(
        SQLEnum(
            CampusVisitSlotStatus,
            name="campusvisitslotstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=CampusVisitSlotStatus.DRAFT,
        nullable=False,
    )
    title = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), nullable=True)

    campus = relationship("Campus", back_populates="visit_slots")
    bookings = relationship(
        "CampusVisitBooking",
        back_populates="slot",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("capacity >= 1", name="ck_campus_visit_slot_capacity_positive"),
        CheckConstraint("ends_at > starts_at", name="ck_campus_visit_slot_end_after_start"),
        Index("ix_campus_visit_slot_campus_start", "campus_id", "starts_at"),
    )

    def filled(self, session: Session) -> int:
        """Count bookings that still occupy capacity (all statuses except cancelled)."""
        stmt = (
            select(sqla_func.count())
            .select_from(CampusVisitBooking)
            .where(
                CampusVisitBooking.slot_id == self.id,
                CampusVisitBooking.status != CampusVisitBookingStatus.CANCELLED,
            )
        )
        return int(session.scalar(stmt) or 0)

    def remaining(self, session: Session) -> int:
        """Seats left for new bookings; never below zero."""
        return max(0, self.capacity - self.filled(session))


class CampusVisitBooking(Base):
    """Visitor reservation for a campus visit slot."""

    __tablename__ = "campus_visit_bookings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    slot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campus_visit_slots.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    visitor_name = Column(String(150), nullable=False)
    visitor_email = Column(String, nullable=False, index=True)
    visitor_phone = Column(String(30), nullable=False)
    status = Column(
        SQLEnum(
            CampusVisitBookingStatus,
            name="campusvisitbookingstatus",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=CampusVisitBookingStatus.BOOKED,
        nullable=False,
    )
    remarks = Column(Text, nullable=True)
    visited_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    slot = relationship("CampusVisitSlot", back_populates="bookings")
    user = relationship("User", back_populates="campus_visit_bookings")

    __table_args__ = (
        UniqueConstraint("slot_id", "visitor_email", name="uq_campus_visit_booking_slot_email"),
        Index("ix_campus_visit_booking_slot_status", "slot_id", "status"),
    )
