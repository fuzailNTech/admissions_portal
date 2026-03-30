"""drop domicile_district from profiles and snapshots

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-03-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q8r9s0t1u2v3"
down_revision: Union[str, Sequence[str], None] = "p7q8r9s0t1u2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_student_profile_domicile", table_name="student_profiles")
    op.drop_column("student_profiles", "domicile_district")
    op.drop_column("application_snapshots", "domicile_district")


def downgrade() -> None:
    op.add_column(
        "student_profiles",
        sa.Column(
            "domicile_district",
            sa.String(length=100),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "application_snapshots",
        sa.Column(
            "domicile_district",
            sa.String(length=100),
            nullable=False,
            server_default="",
        ),
    )
    op.create_index(
        "ix_student_profile_domicile",
        "student_profiles",
        ["domicile_province", "domicile_district"],
        unique=False,
    )
    op.alter_column("student_profiles", "domicile_district", server_default=None)
    op.alter_column("application_snapshots", "domicile_district", server_default=None)
