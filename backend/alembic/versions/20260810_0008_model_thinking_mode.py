"""Add per-role model thinking mode control.

Revision ID: 20260810_0008
Revises: 20260810_0007
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260810_0008"
down_revision = "20260810_0007"
branch_labels = None
depends_on = None

SCHEMA = "lore_app"


def upgrade() -> None:
    columns = {
        str(item["name"])
        for item in sa.inspect(op.get_bind()).get_columns(
            "model_connection_settings", schema=SCHEMA
        )
    }
    if "disable_thinking" in columns:
        return
    op.add_column(
        "model_connection_settings",
        sa.Column("disable_thinking", sa.Boolean(), server_default=sa.false(), nullable=False),
        schema=SCHEMA,
    )
    op.alter_column(
        "model_connection_settings", "disable_thinking", server_default=None, schema=SCHEMA
    )


def downgrade() -> None:
    columns = {
        str(item["name"])
        for item in sa.inspect(op.get_bind()).get_columns(
            "model_connection_settings", schema=SCHEMA
        )
    }
    if "disable_thinking" in columns:
        op.drop_column("model_connection_settings", "disable_thinking", schema=SCHEMA)
