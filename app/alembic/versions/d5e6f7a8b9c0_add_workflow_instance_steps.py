"""add workflow_instance_steps table

Revision ID: d5e6f7a8b9c0
Revises: 6f18e014b988
Create Date: 2026-03-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "6f18e014b988"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_instance_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_instance_id", sa.UUID(), nullable=False),
        sa.Column("subflow_key", sa.String(), nullable=False),
        sa.Column("subflow_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("called_element", sa.String(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("current_tasks", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_instance_id"],
            ["workflow_instances.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_instance_id",
            "called_element",
            name="uq_workflow_instance_step_instance_called",
        ),
    )
    op.create_index(
        op.f("ix_workflow_instance_steps_workflow_instance_id"),
        "workflow_instance_steps",
        ["workflow_instance_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_instance_steps_subflow_key"),
        "workflow_instance_steps",
        ["subflow_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_instance_steps_status"),
        "workflow_instance_steps",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_workflow_instance_steps_status"),
        table_name="workflow_instance_steps",
    )
    op.drop_index(
        op.f("ix_workflow_instance_steps_subflow_key"),
        table_name="workflow_instance_steps",
    )
    op.drop_index(
        op.f("ix_workflow_instance_steps_workflow_instance_id"),
        table_name="workflow_instance_steps",
    )
    op.drop_table("workflow_instance_steps")
