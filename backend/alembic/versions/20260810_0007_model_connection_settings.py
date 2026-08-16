"""Add persistent role-based model connection settings.

Revision ID: 20260810_0007
Revises: 20260809_0006
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260810_0007"
down_revision = "20260809_0006"
branch_labels = None
depends_on = None

SCHEMA = "lore_app"


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("model_connection_settings", schema=SCHEMA):
        return
    op.create_table(
        "model_connection_settings",
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=300), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("context_budget", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("role"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("model_connection_settings", schema=SCHEMA):
        op.drop_table("model_connection_settings", schema=SCHEMA)
