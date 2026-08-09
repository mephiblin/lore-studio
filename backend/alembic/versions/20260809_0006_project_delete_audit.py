"""Preserve project deletion audits after the owning project is removed.

Revision ID: 20260809_0006
Revises: 20260809_0005
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260809_0006"
down_revision = "20260809_0005"
branch_labels = None
depends_on = None

SCHEMA = "lore_app"


def _project_fk_name() -> str | None:
    for item in sa.inspect(op.get_bind()).get_foreign_keys("audit_logs", schema=SCHEMA):
        if list(item.get("constrained_columns") or []) == ["project_id"] and item.get("name"):
            return str(item["name"])
    return None


def upgrade() -> None:
    foreign_key = _project_fk_name()
    if foreign_key:
        op.drop_constraint(foreign_key, "audit_logs", schema=SCHEMA, type_="foreignkey")
    op.alter_column("audit_logs", "project_id", nullable=True, schema=SCHEMA)
    op.create_foreign_key(
        "fk_audit_logs_project_tombstone",
        "audit_logs",
        "projects",
        ["project_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )


def downgrade() -> None:
    foreign_key = _project_fk_name()
    if foreign_key:
        op.drop_constraint(foreign_key, "audit_logs", schema=SCHEMA, type_="foreignkey")
    op.execute("DELETE FROM lore_app.audit_logs WHERE project_id IS NULL")
    op.alter_column("audit_logs", "project_id", nullable=False, schema=SCHEMA)
    op.create_foreign_key(
        "audit_logs_project_id_fkey",
        "audit_logs",
        "projects",
        ["project_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )
