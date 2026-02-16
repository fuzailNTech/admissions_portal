"""convert_enums_to_lowercase

Revision ID: 5695f548513a
Revises: bf6f233c8711
Create Date: 2026-02-16 23:47:23.973674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5695f548513a'
down_revision: Union[str, Sequence[str], None] = 'bf6f233c8711'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
