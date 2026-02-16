"""add application number sequences

Revision ID: 153dfe4caff4
Revises: 5695f548513a
Create Date: 2026-02-17 04:11:25.425951

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '153dfe4caff4'
down_revision: Union[str, Sequence[str], None] = '5695f548513a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
