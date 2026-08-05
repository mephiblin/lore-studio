"""Separate editable draft blocks from the polished final body.

Revision ID: 20260805_0002
Revises: 20260805_0001
Create Date: 2026-08-05
"""

import sqlalchemy as sa

from alembic import op

revision = "20260805_0002"
down_revision = "20260805_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lore_documents",
        sa.Column("final_body_markdown", sa.Text(), nullable=False, server_default=""),
        schema="lore_app",
        if_not_exists=True,
    )
    op.add_column(
        "lore_documents",
        sa.Column("finalized_from_hash", sa.String(length=128), nullable=False, server_default=""),
        schema="lore_app",
        if_not_exists=True,
    )
    op.add_column(
        "lore_documents",
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        schema="lore_app",
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column("lore_documents", "finalized_at", schema="lore_app", if_exists=True)
    op.drop_column("lore_documents", "finalized_from_hash", schema="lore_app", if_exists=True)
    op.drop_column("lore_documents", "final_body_markdown", schema="lore_app", if_exists=True)
