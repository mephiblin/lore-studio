"""Connect versioned voice profiles and approved style examples to playbooks.

Revision ID: 20260809_0005
Revises: 20260808_0004
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260809_0005"
down_revision = "20260808_0004"
branch_labels = None
depends_on = None

SCHEMA = "lore_app"


def _columns(table: str) -> dict[str, dict[str, object]]:
    return {str(item["name"]): item for item in sa.inspect(op.get_bind()).get_columns(table, schema=SCHEMA)}


def _indexes(table: str) -> set[str]:
    return {
        str(item["name"])
        for item in sa.inspect(op.get_bind()).get_indexes(table, schema=SCHEMA)
        if item.get("name")
    }


def _has_foreign_key(table: str, columns: list[str]) -> bool:
    return any(
        list(item.get("constrained_columns") or []) == columns
        for item in sa.inspect(op.get_bind()).get_foreign_keys(table, schema=SCHEMA)
    )


def _foreign_key_name(table: str, columns: list[str]) -> str | None:
    for item in sa.inspect(op.get_bind()).get_foreign_keys(table, schema=SCHEMA):
        if list(item.get("constrained_columns") or []) == columns and item.get("name"):
            return str(item["name"])
    return None


def upgrade() -> None:
    profile_columns = _columns("voice_profiles")
    if "key" not in profile_columns:
        op.add_column("voice_profiles", sa.Column("key", sa.String(120), nullable=True), schema=SCHEMA)
    if "version" not in profile_columns:
        op.add_column(
            "voice_profiles",
            sa.Column("version", sa.String(40), nullable=False, server_default="1.0.0"),
            schema=SCHEMA,
        )
    if "description" not in profile_columns:
        op.add_column(
            "voice_profiles",
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            schema=SCHEMA,
        )
    if "is_builtin" not in profile_columns:
        op.add_column(
            "voice_profiles",
            sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
            schema=SCHEMA,
        )
    if "status" not in profile_columns:
        op.add_column(
            "voice_profiles",
            sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
            schema=SCHEMA,
        )
    if "approved" in profile_columns:
        op.execute(
            """
        UPDATE lore_app.voice_profiles
           SET key = CASE
               WHEN source_analysis_id IS NOT NULL
                   THEN 'reference_' || substring(replace(source_analysis_id, '-', '') from 1 for 12)
               ELSE 'voice_' || substring(replace(id, '-', '') from 1 for 12)
           END,
               status = CASE WHEN approved THEN 'APPROVED' ELSE 'DRAFT' END,
               description = COALESCE(profile_json ->> 'reader_effect', '')
            """
        )
    profile_columns = _columns("voice_profiles")
    if bool(profile_columns["key"].get("nullable")):
        op.alter_column("voice_profiles", "key", nullable=False, schema=SCHEMA)
    if not bool(profile_columns["project_id"].get("nullable")):
        op.alter_column("voice_profiles", "project_id", nullable=True, schema=SCHEMA)
    profile_indexes = _indexes("voice_profiles")
    if "uq_voice_profile_project_key_version" not in profile_indexes:
        op.create_index(
            "uq_voice_profile_project_key_version",
            "voice_profiles",
            ["project_id", "key", "version"],
            unique=True,
            schema=SCHEMA,
            postgresql_where=sa.text("project_id IS NOT NULL"),
        )
    if "uq_voice_profile_shared_key_version" not in profile_indexes:
        op.create_index(
            "uq_voice_profile_shared_key_version",
            "voice_profiles",
            ["key", "version"],
            unique=True,
            schema=SCHEMA,
            postgresql_where=sa.text("project_id IS NULL"),
        )
    if not any("source_analysis_id" in name for name in profile_indexes):
        op.create_index(
            "ix_voice_profiles_source_analysis_id",
            "voice_profiles",
            ["source_analysis_id"],
            schema=SCHEMA,
        )
    if not any(
        name.endswith("voice_profiles_status") or name == "ix_voice_profiles_status"
        for name in profile_indexes
    ):
        op.create_index("ix_voice_profiles_status", "voice_profiles", ["status"], schema=SCHEMA)
    if not _has_foreign_key("voice_profiles", ["source_analysis_id"]):
        op.create_foreign_key(
            "fk_voice_profiles_source_analysis",
            "voice_profiles",
            "reference_analyses",
            ["source_analysis_id"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
            ondelete="SET NULL",
        )
    if "approved" in profile_columns:
        op.drop_column("voice_profiles", "approved", schema=SCHEMA)

    if not sa.inspect(op.get_bind()).has_table("voice_profile_examples", schema=SCHEMA):
        op.create_table(
            "voice_profile_examples",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("voice_profile_id", sa.String(36), nullable=False),
            sa.Column("source_concept_page_id", sa.String(36), nullable=True),
            sa.Column("label", sa.String(300), nullable=False),
            sa.Column("excerpt", sa.Text(), nullable=False),
            sa.Column("teaches_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
            sa.Column("scene_tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
            sa.Column("rights_basis", sa.String(32), nullable=False, server_default="ANALYSIS_ONLY"),
            sa.Column("use_in_generation", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
            sa.Column("excerpt_hash", sa.String(128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["voice_profile_id"],
                [f"{SCHEMA}.voice_profiles.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["source_concept_page_id"],
                [f"{SCHEMA}.concept_pages.id"],
                ondelete="SET NULL",
            ),
            schema=SCHEMA,
        )
    example_indexes = _indexes("voice_profile_examples")
    if "ix_voice_profile_examples_profile" not in example_indexes:
        op.create_index(
            "ix_voice_profile_examples_profile",
            "voice_profile_examples",
            ["voice_profile_id", "status", "position"],
            schema=SCHEMA,
        )
    if "ix_voice_profile_examples_source_page" not in example_indexes:
        op.create_index(
            "ix_voice_profile_examples_source_page",
            "voice_profile_examples",
            ["source_concept_page_id"],
            schema=SCHEMA,
        )

    session_columns = _columns("playbook_sessions")
    if "voice_selection_mode" not in session_columns:
        op.add_column(
            "playbook_sessions",
            sa.Column(
                "voice_selection_mode",
                sa.String(32),
                nullable=False,
                server_default="model_default",
            ),
            schema=SCHEMA,
        )
    if "voice_example_ids" not in session_columns:
        op.add_column(
            "playbook_sessions",
            sa.Column("voice_example_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
            schema=SCHEMA,
        )


def downgrade() -> None:
    session_columns = _columns("playbook_sessions")
    if "voice_example_ids" in session_columns:
        op.drop_column("playbook_sessions", "voice_example_ids", schema=SCHEMA)
    if "voice_selection_mode" in session_columns:
        op.drop_column("playbook_sessions", "voice_selection_mode", schema=SCHEMA)
    if sa.inspect(op.get_bind()).has_table("voice_profile_examples", schema=SCHEMA):
        op.drop_table("voice_profile_examples", schema=SCHEMA)

    profile_columns = _columns("voice_profiles")
    if "approved" not in profile_columns:
        op.add_column(
            "voice_profiles",
            sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
            schema=SCHEMA,
        )
    op.execute("UPDATE lore_app.voice_profiles SET approved = (status = 'APPROVED')")
    source_foreign_key = _foreign_key_name("voice_profiles", ["source_analysis_id"])
    if source_foreign_key:
        op.drop_constraint(source_foreign_key, "voice_profiles", schema=SCHEMA, type_="foreignkey")
    profile_indexes = _indexes("voice_profiles")
    for index_name in (
        "ix_voice_profiles_status",
        "ix_lore_app_voice_profiles_status",
        "ix_voice_profiles_source_analysis_id",
        "ix_lore_app_voice_profiles_source_analysis_id",
        "uq_voice_profile_shared_key_version",
        "uq_voice_profile_project_key_version",
    ):
        if index_name in profile_indexes:
            op.drop_index(index_name, table_name="voice_profiles", schema=SCHEMA)
    op.execute("DELETE FROM lore_app.voice_profiles WHERE project_id IS NULL")
    op.alter_column("voice_profiles", "project_id", nullable=False, schema=SCHEMA)
    for column_name in ("status", "is_builtin", "description", "version", "key"):
        if column_name in profile_columns:
            op.drop_column("voice_profiles", column_name, schema=SCHEMA)
