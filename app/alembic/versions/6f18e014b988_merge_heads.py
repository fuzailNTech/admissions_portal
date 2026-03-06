"""merge_heads

Revision ID: 6f18e014b988
Revises: 1a10fde2a385, c4d5e6f7a8b9
Create Date: 2026-03-04 02:35:32.999835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f18e014b988'
down_revision: Union[str, Sequence[str], None] = ('1a10fde2a385', 'c4d5e6f7a8b9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
