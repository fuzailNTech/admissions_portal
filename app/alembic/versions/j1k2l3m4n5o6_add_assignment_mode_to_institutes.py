"""add application_assignment_mode to institutes

Revision ID: j1k2l3m4n5o6
Revises: 6f18e014b988
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "j1k2l3m4n5o6"
down_revision: Union[str, Sequence[str], None] = "i0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


assignmentmode = sa.Enum("auto", "manual", name="assignmentmode")


def upgrade() -> None:
    assignmentmode.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "institutes",
        sa.Column(
            "application_assignment_mode",
            assignmentmode,
            server_default="auto",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("institutes", "application_assignment_mode")
    assignmentmode.drop(op.get_bind(), checkfirst=True)
