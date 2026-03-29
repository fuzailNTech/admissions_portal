"""add campus visit slots and bookings

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-03-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID


revision: str = "p7q8r9s0t1u2"
down_revision: Union[str, Sequence[str], None] = "o6p7q8r9s0t1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: types may already exist after a failed run that died on create_table.
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE campusvisitslotstatus AS ENUM (
                'draft', 'published', 'paused', 'closed'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE campusvisitbookingstatus AS ENUM (
                'booked', 'visited', 'cancelled', 'no_show'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "campus_visit_slots",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("campus_id", UUID(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            ENUM(
                "draft",
                "published",
                "paused",
                "closed",
                name="campusvisitslotstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("capacity >= 1", name="ck_campus_visit_slot_capacity_positive"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_campus_visit_slot_end_after_start"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campus_visit_slots_status", "campus_visit_slots", ["status"])
    op.create_index(
        "ix_campus_visit_slot_campus_start",
        "campus_visit_slots",
        ["campus_id", "starts_at"],
    )

    op.create_table(
        "campus_visit_bookings",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("slot_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("visitor_name", sa.String(length=150), nullable=False),
        sa.Column("visitor_email", sa.String(), nullable=False),
        sa.Column("visitor_phone", sa.String(length=30), nullable=False),
        sa.Column(
            "status",
            ENUM(
                "booked",
                "visited",
                "cancelled",
                "no_show",
                name="campusvisitbookingstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="booked",
        ),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["slot_id"], ["campus_visit_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_id", "visitor_email", name="uq_campus_visit_booking_slot_email"),
    )
    op.create_index("ix_campus_visit_bookings_user_id", "campus_visit_bookings", ["user_id"])
    op.create_index("ix_campus_visit_bookings_visitor_email", "campus_visit_bookings", ["visitor_email"])
    op.create_index("ix_campus_visit_bookings_status", "campus_visit_bookings", ["status"])
    op.create_index(
        "ix_campus_visit_booking_slot_status",
        "campus_visit_bookings",
        ["slot_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_campus_visit_booking_slot_status", table_name="campus_visit_bookings")
    op.drop_index("ix_campus_visit_bookings_status", table_name="campus_visit_bookings")
    op.drop_index("ix_campus_visit_bookings_visitor_email", table_name="campus_visit_bookings")
    op.drop_index("ix_campus_visit_bookings_user_id", table_name="campus_visit_bookings")
    op.drop_table("campus_visit_bookings")

    op.drop_index("ix_campus_visit_slot_campus_start", table_name="campus_visit_slots")
    op.drop_index("ix_campus_visit_slots_status", table_name="campus_visit_slots")
    op.drop_table("campus_visit_slots")

    op.execute("DROP TYPE campusvisitbookingstatus")
    op.execute("DROP TYPE campusvisitslotstatus")
