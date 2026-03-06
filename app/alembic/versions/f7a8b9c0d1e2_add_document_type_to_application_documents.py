"""add document_type to application_documents

Revision ID: f7a8b9c0d1e2
Revises: 6f18e014b988
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE documenttype AS ENUM "
        "('profile_picture', 'identity_document', 'academic_result_card', 'other')"
    )
    op.add_column(
        "application_documents",
        sa.Column(
            "document_type",
            sa.Enum(
                "profile_picture",
                "identity_document",
                "academic_result_card",
                "other",
                name="documenttype",
            ),
            nullable=False,
            server_default="other",
        ),
    )
    op.create_index(
        "ix_application_documents_document_type",
        "application_documents",
        ["document_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_application_documents_document_type",
        table_name="application_documents",
    )
    op.drop_column("application_documents", "document_type")
    op.execute("DROP TYPE documenttype")
