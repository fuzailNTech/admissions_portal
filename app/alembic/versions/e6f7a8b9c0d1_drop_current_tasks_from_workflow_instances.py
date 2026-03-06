"""drop current_tasks from workflow_instances

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-03-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("workflow_instances", "current_tasks")


def downgrade() -> None:
    op.add_column(
        "workflow_instances",
        sa.Column("current_tasks", sa.JSON(), nullable=True),
    )
