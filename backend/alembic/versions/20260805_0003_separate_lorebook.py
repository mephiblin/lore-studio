"""Store polished work as separate lorebook documents.

Revision ID: 20260805_0003
Revises: 20260805_0002
Create Date: 2026-08-05
"""

from __future__ import annotations

import json
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20260805_0003"
down_revision = "20260805_0002"
branch_labels = None
depends_on = None

SCHEMA = "lore_app"
TABLE = "lore_documents"


def _columns() -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(TABLE, schema=SCHEMA)}


def _indexes() -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(TABLE, schema=SCHEMA)}


def _foreign_keys() -> set[str]:
    return {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_foreign_keys(TABLE, schema=SCHEMA)
        if item.get("name")
    }


def _body_json(body: str) -> str:
    return json.dumps(
        {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": paragraph}],
                }
                for paragraph in body.split("\n\n")
                if paragraph.strip()
            ],
        },
        ensure_ascii=False,
    )


def upgrade() -> None:
    columns = _columns()
    additions = {
        "document_kind": sa.Column(
            "document_kind", sa.String(length=32), nullable=False, server_default="draft"
        ),
        "source_document_id": sa.Column("source_document_id", sa.String(length=36), nullable=True),
        "source_draft_hash": sa.Column(
            "source_draft_hash", sa.String(length=128), nullable=False, server_default=""
        ),
        "generation_inputs_json": sa.Column(
            "generation_inputs_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        "published_at": sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column(TABLE, column, schema=SCHEMA)

    if "fk_lore_documents_source_document_id" not in _foreign_keys():
        op.create_foreign_key(
            "fk_lore_documents_source_document_id",
            TABLE,
            TABLE,
            ["source_document_id"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
            ondelete="CASCADE",
        )
    indexes = _indexes()
    if "ix_lore_documents_kind_project" not in indexes:
        op.create_index(
            "ix_lore_documents_kind_project",
            TABLE,
            ["document_kind", "project_id"],
            schema=SCHEMA,
        )
    if "ix_lore_documents_source_document_unique" not in indexes:
        op.create_index(
            "ix_lore_documents_source_document_unique",
            TABLE,
            ["source_document_id"],
            unique=True,
            schema=SCHEMA,
        )

    connection = op.get_bind()
    legacy_rows = connection.execute(
        sa.text(
            """
            SELECT id, project_id, session_id, writing_recipe_id, title,
                   final_body_markdown, finalized_from_hash, finalized_at,
                   created_at, updated_at
              FROM lore_app.lore_documents
             WHERE final_body_markdown <> ''
               AND document_kind = 'draft'
            """
        )
    ).mappings()
    for row in legacy_rows:
        entry_id = str(uuid4())
        body = str(row["final_body_markdown"])
        published_at = row["finalized_at"] or row["updated_at"]
        connection.execute(
            sa.text(
                """
                INSERT INTO lore_app.lore_documents
                    (id, project_id, session_id, writing_recipe_id, title,
                     body_markdown, body_json, document_kind, source_document_id,
                     source_draft_hash, generation_inputs_json, published_at,
                     status, created_at, updated_at)
                VALUES
                    (:id, :project_id, :session_id, :writing_recipe_id, :title,
                     :body_markdown, CAST(:body_json AS json), 'lorebook', :source_document_id,
                     :source_draft_hash, CAST('{}' AS json), :published_at,
                     'approved', :created_at, :updated_at)
                """
            ),
            {
                "id": entry_id,
                "project_id": row["project_id"],
                "session_id": row["session_id"],
                "writing_recipe_id": row["writing_recipe_id"],
                "title": row["title"],
                "body_markdown": body,
                "body_json": _body_json(body),
                "source_document_id": row["id"],
                "source_draft_hash": row["finalized_from_hash"],
                "published_at": published_at,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO lore_app.lore_revisions
                    (id, document_id, revision_number, body_markdown, body_json,
                     reason, author_type, created_at, updated_at)
                VALUES
                    (:id, :document_id, 1, :body_markdown, CAST(:body_json AS json),
                     'migrated_final_body', 'system', :created_at, :updated_at)
                """
            ),
            {
                "id": str(uuid4()),
                "document_id": entry_id,
                "body_markdown": body,
                "body_json": _body_json(body),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )

    for name in ("finalized_at", "finalized_from_hash", "final_body_markdown"):
        if name in _columns():
            op.drop_column(TABLE, name, schema=SCHEMA)


def downgrade() -> None:
    columns = _columns()
    if "final_body_markdown" not in columns:
        op.add_column(
            TABLE,
            sa.Column("final_body_markdown", sa.Text(), nullable=False, server_default=""),
            schema=SCHEMA,
        )
    if "finalized_from_hash" not in columns:
        op.add_column(
            TABLE,
            sa.Column(
                "finalized_from_hash", sa.String(length=128), nullable=False, server_default=""
            ),
            schema=SCHEMA,
        )
    if "finalized_at" not in columns:
        op.add_column(
            TABLE,
            sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
            schema=SCHEMA,
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE lore_app.lore_documents AS source
               SET final_body_markdown = entry.body_markdown,
                   finalized_from_hash = entry.source_draft_hash,
                   finalized_at = entry.published_at
              FROM lore_app.lore_documents AS entry
             WHERE entry.document_kind = 'lorebook'
               AND entry.source_document_id = source.id
            """
        )
    )
    connection.execute(
        sa.text("DELETE FROM lore_app.lore_documents WHERE document_kind = 'lorebook'")
    )

    indexes = _indexes()
    if "ix_lore_documents_source_document_unique" in indexes:
        op.drop_index("ix_lore_documents_source_document_unique", table_name=TABLE, schema=SCHEMA)
    if "ix_lore_documents_kind_project" in indexes:
        op.drop_index("ix_lore_documents_kind_project", table_name=TABLE, schema=SCHEMA)
    if "fk_lore_documents_source_document_id" in _foreign_keys():
        op.drop_constraint(
            "fk_lore_documents_source_document_id", TABLE, schema=SCHEMA, type_="foreignkey"
        )
    for name in (
        "published_at",
        "generation_inputs_json",
        "source_draft_hash",
        "source_document_id",
        "document_kind",
    ):
        if name in _columns():
            op.drop_column(TABLE, name, schema=SCHEMA)
