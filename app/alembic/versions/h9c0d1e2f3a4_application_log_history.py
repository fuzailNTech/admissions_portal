"""application_log_history

Replace application_status_history with application_log_history for a general
audit log of every action on an application (action_type + details text).

Revision ID: h9c0d1e2f3a4
Revises: g8b9c0d1e2f3
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "h9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "g8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_log_history",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("changed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", name="uq_application_log_history_id"),
    )
    op.create_index(
        "ix_application_log_history_application_id",
        "application_log_history",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        "ix_application_log_history_action_type",
        "application_log_history",
        ["action_type"],
        unique=False,
    )
    op.create_index(
        "ix_log_history_application_created",
        "application_log_history",
        ["application_id", "created_at"],
        unique=False,
    )

    # Migrate data from application_status_history (details = notes)
    op.execute(
        """
        INSERT INTO application_log_history (id, application_id, action_type, details, changed_by, created_at)
        SELECT
            id,
            application_id,
            'status_change',
            notes,
            changed_by,
            created_at
        FROM application_status_history
        """
    )

    # Drop old table (indexes and constraints dropped with table)
    op.drop_table("application_status_history")


def downgrade() -> None:
    op.create_table(
        "application_status_history",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "from_status",
            sa.Enum("submitted", "under_review", "documents_pending", "verified", "offered", "rejected", "accepted", "withdrawn", name="applicationstatus"),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.Enum("submitted", "under_review", "documents_pending", "verified", "offered", "rejected", "accepted", "withdrawn", name="applicationstatus"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("changed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", name="uq_application_status_history_id"),
    )
    op.create_index(
        op.f("ix_application_status_history_application_id"),
        "application_status_history",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        "ix_status_history_application_created",
        "application_status_history",
        ["application_id", "created_at"],
        unique=False,
    )

    # Migrate back: only rows with action_type = 'status_change' (details becomes notes; from/to_status lost)
    op.execute(
        """
        INSERT INTO application_status_history (id, application_id, from_status, to_status, notes, changed_by, created_at)
        SELECT
            id,
            application_id,
            NULL,
            'submitted',
            details,
            changed_by,
            created_at
        FROM application_log_history
        WHERE action_type = 'status_change'
        """
    )

    op.drop_index("ix_log_history_application_created", table_name="application_log_history")
    op.drop_index("ix_application_log_history_action_type", table_name="application_log_history")
    op.drop_index("ix_application_log_history_application_id", table_name="application_log_history")
    op.drop_table("application_log_history")
