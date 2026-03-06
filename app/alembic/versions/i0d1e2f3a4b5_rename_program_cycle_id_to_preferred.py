"""rename program_cycle_id to preferred_program_cycle_id on applications

Revision ID: i0d1e2f3a4b5
Revises: h9c0d1e2f3a4
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op


revision: str = "i0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "h9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "applications",
        "program_cycle_id",
        new_column_name="preferred_program_cycle_id",
    )


def downgrade() -> None:
    op.alter_column(
        "applications",
        "preferred_program_cycle_id",
        new_column_name="program_cycle_id",
    )
