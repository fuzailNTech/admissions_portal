"""add upload_tokens table

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-03-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, Sequence[str], None] = "l3m4n5o6p7q8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "upload_tokens",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_upload_tokens_token", "upload_tokens", ["token"], unique=True)
    op.create_index("ix_upload_tokens_expires_at", "upload_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_upload_tokens_expires_at", table_name="upload_tokens")
    op.drop_index("ix_upload_tokens_token", table_name="upload_tokens")
    op.drop_table("upload_tokens")
