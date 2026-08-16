"""Remove unused embedding retrieval storage and settings.

Revision ID: 20260813_0009
Revises: 20260810_0008
Create Date: 2026-08-13
"""

from __future__ import annotations

from alembic import op

revision = "20260813_0009"
down_revision = "20260810_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS lore_app.index_jobs")
    op.execute("DROP SCHEMA IF EXISTS lore_vector CASCADE")
    op.execute("DELETE FROM lore_app.model_connection_settings WHERE role = 'embedding'")
    op.execute("DROP EXTENSION IF EXISTS vector")


def downgrade() -> None:
    raise RuntimeError(
        "20260813_0009 removes derived embedding vectors and queued index jobs permanently. "
        "Restore a pre-migration backup to return to the embedding architecture."
    )
