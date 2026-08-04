"""Lore Studio v1 PostgreSQL and pgvector schema.

Revision ID: 20260805_0001
Revises:
Create Date: 2026-08-05
"""

from alembic import op
from app import models  # noqa: F401
from app.db import Base

revision = "20260805_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS lore_app")
    op.execute("CREATE SCHEMA IF NOT EXISTS lore_vector")
    Base.metadata.create_all(bind=connection, checkfirst=True)


def downgrade() -> None:
    connection = op.get_bind()
    for table in reversed(Base.metadata.sorted_tables):
        table.drop(bind=connection, checkfirst=True)
    op.execute("DROP SCHEMA IF EXISTS lore_vector")
    op.execute("DROP SCHEMA IF EXISTS lore_app")
