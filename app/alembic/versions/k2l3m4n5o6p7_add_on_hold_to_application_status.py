"""add on_hold to application status enum

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op


revision: str = "k2l3m4n5o6p7"
down_revision: Union[str, Sequence[str], None] = "j1k2l3m4n5o6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE applicationstatus ADD VALUE IF NOT EXISTS 'on_hold'")


def downgrade() -> None:
    # PostgreSQL does not support removing an enum value; leave as no-op.
    pass
