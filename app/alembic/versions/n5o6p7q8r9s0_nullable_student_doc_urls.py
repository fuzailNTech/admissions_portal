"""nullable student profile and academic record doc URLs

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n5o6p7q8r9s0"
down_revision: Union[str, Sequence[str], None] = "m4n5o6p7q8r9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "student_profiles",
        "profile_picture_url",
        existing_type=sa.String(500),
        nullable=True,
    )
    op.alter_column(
        "student_profiles",
        "identity_doc_url",
        existing_type=sa.String(500),
        nullable=True,
    )
    op.alter_column(
        "student_academic_records",
        "result_card_url",
        existing_type=sa.String(500),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "student_academic_records",
        "result_card_url",
        existing_type=sa.String(500),
        nullable=False,
    )
    op.alter_column(
        "student_profiles",
        "identity_doc_url",
        existing_type=sa.String(500),
        nullable=False,
    )
    op.alter_column(
        "student_profiles",
        "profile_picture_url",
        existing_type=sa.String(500),
        nullable=False,
    )
