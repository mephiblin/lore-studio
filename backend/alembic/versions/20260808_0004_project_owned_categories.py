"""Make concept-page categories project-owned and enforce their scope.

Revision ID: 20260808_0004
Revises: 20260805_0003
Create Date: 2026-08-08
"""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20260808_0004"
down_revision = "20260805_0003"
branch_labels = None
depends_on = None

SCHEMA = "lore_app"
DEFAULTS = {
    "artifact": ("유물·기술", ["subject", "elements"]),
    "event": ("사건", ["subject", "background", "elements", "conflicts"]),
    "free": ("자유 페이지", ["subject", "background", "elements", "conflicts"]),
    "person": ("인물", ["subject", "elements", "conflicts"]),
    "place": ("장소", ["subject", "background"]),
}


def _foreign_keys() -> set[str]:
    return {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_foreign_keys(
            "concept_pages", schema=SCHEMA
        )
        if item.get("name")
    }


def _insert_category(
    connection: sa.Connection,
    project_id: str,
    key: str,
    name: str,
    description: str = "",
    template_json: dict[str, object] | None = None,
) -> None:
    exists = connection.execute(
        sa.text(
            """
            SELECT 1 FROM lore_app.category_definitions
             WHERE project_id = :project_id AND key = :key
            """
        ),
        {"project_id": project_id, "key": key},
    ).first()
    if exists:
        return
    connection.execute(
        sa.text(
            """
            INSERT INTO lore_app.category_definitions
                (id, project_id, key, name, description, template_json,
                 is_builtin, created_at, updated_at)
            VALUES
                (:id, :project_id, :key, :name, :description,
                 CAST(:template_json AS json), false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {
            "id": str(uuid4()),
            "project_id": project_id,
            "key": key,
            "name": name,
            "description": description,
            "template_json": json.dumps(template_json or {}, ensure_ascii=False),
        },
    )


def _key_for_custom_name(connection: sa.Connection, project_id: str, name: str) -> str:
    existing = connection.execute(
        sa.text(
            """
            SELECT key FROM lore_app.category_definitions
             WHERE project_id = :project_id AND name = :name
             ORDER BY created_at LIMIT 1
            """
        ),
        {"project_id": project_id, "name": name},
    ).scalar_one_or_none()
    if existing:
        return str(existing)
    digest = hashlib.sha1(f"{project_id}:{name}".encode()).hexdigest()[:12]
    key = f"custom-{digest}"
    _insert_category(
        connection,
        project_id,
        key,
        name,
        "기존 사용자 정의 종류에서 이전됨",
        {"recommended_slots": ["subject", "background", "elements", "conflicts"]},
    )
    return key


def upgrade() -> None:
    connection = op.get_bind()
    projects = [
        str(row[0])
        for row in connection.execute(sa.text("SELECT id FROM lore_app.projects")).all()
    ]
    global_categories = connection.execute(
        sa.text(
            """
            SELECT key, name, description, template_json
              FROM lore_app.category_definitions
             WHERE project_id IS NULL
            """
        )
    ).mappings().all()

    for project_id in projects:
        for category in global_categories:
            template = category["template_json"] or {}
            if isinstance(template, str):
                template = json.loads(template)
            _insert_category(
                connection,
                project_id,
                str(category["key"]),
                str(category["name"]),
                str(category["description"] or ""),
                dict(template),
            )
        for key, (name, slots) in DEFAULTS.items():
            _insert_category(
                connection,
                project_id,
                key,
                name,
                template_json={"recommended_slots": slots},
            )

        custom_names = connection.execute(
            sa.text(
                """
                SELECT DISTINCT custom_category
                  FROM lore_app.concept_pages
                 WHERE project_id = :project_id AND custom_category <> ''
                """
            ),
            {"project_id": project_id},
        ).scalars()
        for custom_name in custom_names:
            name = str(custom_name).strip()
            if not name:
                continue
            key = _key_for_custom_name(connection, project_id, name)
            connection.execute(
                sa.text(
                    """
                    UPDATE lore_app.concept_pages
                       SET category_key = :key
                     WHERE project_id = :project_id AND custom_category = :name
                    """
                ),
                {"key": key, "project_id": project_id, "name": custom_name},
            )

        used_keys = connection.execute(
            sa.text(
                """
                SELECT DISTINCT category_key
                  FROM lore_app.concept_pages
                 WHERE project_id = :project_id
                UNION
                SELECT DISTINCT category_key
                  FROM lore_app.proposed_concept_updates
                 WHERE project_id = :project_id
                """
            ),
            {"project_id": project_id},
        ).scalars()
        for used_key in used_keys:
            key = str(used_key or "free")
            name = DEFAULTS.get(key, (key, []))[0]
            _insert_category(
                connection,
                project_id,
                key,
                name,
                template_json={
                    "recommended_slots": DEFAULTS.get(
                        key,
                        ("", ["subject", "background", "elements", "conflicts"]),
                    )[1]
                },
            )

    connection.execute(
        sa.text("DELETE FROM lore_app.category_definitions WHERE project_id IS NULL")
    )
    connection.execute(
        sa.text("UPDATE lore_app.category_definitions SET is_builtin = false")
    )
    op.alter_column(
        "category_definitions",
        "project_id",
        existing_type=sa.String(length=36),
        nullable=False,
        schema=SCHEMA,
    )
    if "fk_concept_page_project_category" not in _foreign_keys():
        op.create_foreign_key(
            "fk_concept_page_project_category",
            "concept_pages",
            "category_definitions",
            ["project_id", "category_key"],
            ["project_id", "key"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    if "fk_concept_page_project_category" in _foreign_keys():
        op.drop_constraint(
            "fk_concept_page_project_category",
            "concept_pages",
            schema=SCHEMA,
            type_="foreignkey",
        )
    op.alter_column(
        "category_definitions",
        "project_id",
        existing_type=sa.String(length=36),
        nullable=True,
        schema=SCHEMA,
    )
