"""step link to workflow_catalog

Replace subflow_key, subflow_version, called_element on workflow_instance_steps
with workflow_catalog_id FK. Single source of truth from workflow_catalog.

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable FK first
    op.add_column(
        "workflow_instance_steps",
        sa.Column(
            "workflow_catalog_id",
            sa.UUID(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_workflow_instance_steps_workflow_catalog_id",
        "workflow_instance_steps",
        "workflow_catalog",
        ["workflow_catalog_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Backfill from catalog by (subflow_key, subflow_version)
    op.execute(
        """
        UPDATE workflow_instance_steps s
        SET workflow_catalog_id = c.id
        FROM workflow_catalog c
        WHERE c.subflow_key = s.subflow_key AND c.version = s.subflow_version
        """
    )

    # Drop old constraint and index
    op.drop_constraint(
        "uq_workflow_instance_step_instance_called",
        "workflow_instance_steps",
        type_="unique",
    )
    op.drop_index(
        "ix_workflow_instance_steps_subflow_key",
        table_name="workflow_instance_steps",
    )

    # Drop old columns
    op.drop_column("workflow_instance_steps", "subflow_key")
    op.drop_column("workflow_instance_steps", "subflow_version")
    op.drop_column("workflow_instance_steps", "called_element")

    # Make FK NOT NULL
    op.alter_column(
        "workflow_instance_steps",
        "workflow_catalog_id",
        existing_type=sa.UUID(),
        nullable=False,
    )

    # Index and new unique constraint
    op.create_index(
        "ix_workflow_instance_steps_workflow_catalog_id",
        "workflow_instance_steps",
        ["workflow_catalog_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_workflow_instance_step_instance_catalog",
        "workflow_instance_steps",
        ["workflow_instance_id", "workflow_catalog_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_workflow_instance_step_instance_catalog",
        "workflow_instance_steps",
        type_="unique",
    )
    op.drop_index(
        "ix_workflow_instance_steps_workflow_catalog_id",
        table_name="workflow_instance_steps",
    )

    op.add_column(
        "workflow_instance_steps",
        sa.Column("subflow_key", sa.String(), nullable=True),
    )
    op.add_column(
        "workflow_instance_steps",
        sa.Column("subflow_version", sa.Integer(), nullable=True, server_default=sa.text("1")),
    )
    op.add_column(
        "workflow_instance_steps",
        sa.Column("called_element", sa.String(), nullable=True),
    )

    # Backfill from catalog
    op.execute(
        """
        UPDATE workflow_instance_steps s
        SET subflow_key = c.subflow_key,
            subflow_version = c.version,
            called_element = c.process_id
        FROM workflow_catalog c
        WHERE c.id = s.workflow_catalog_id
        """
    )
    op.alter_column(
        "workflow_instance_steps",
        "subflow_key",
        existing_type=sa.String(),
        nullable=False,
    )
    op.alter_column(
        "workflow_instance_steps",
        "subflow_version",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "workflow_instance_steps",
        "called_element",
        existing_type=sa.String(),
        nullable=False,
    )

    op.drop_constraint(
        "fk_workflow_instance_steps_workflow_catalog_id",
        "workflow_instance_steps",
        type_="foreignkey",
    )
    op.drop_column("workflow_instance_steps", "workflow_catalog_id")

    op.create_index(
        "ix_workflow_instance_steps_subflow_key",
        "workflow_instance_steps",
        ["subflow_key"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_workflow_instance_step_instance_called",
        "workflow_instance_steps",
        ["workflow_instance_id", "called_element"],
    )
