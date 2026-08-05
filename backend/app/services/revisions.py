from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ConceptPage, ConceptPageRevision, LoreDocument, LoreRevision


def concept_snapshot(page: ConceptPage) -> dict[str, Any]:
    return {
        key: getattr(page, key)
        for key in (
            "title",
            "category_key",
            "custom_category",
            "tags",
            "usage_role",
            "authority_state",
            "status",
            "namespace",
            "era",
            "continuity",
            "summary",
            "body_json",
            "properties_json",
            "locked_facts",
            "open_questions",
            "forbidden_changes",
            "attachment_refs",
        )
    }


def add_concept_revision(
    db: Session,
    page: ConceptPage,
    *,
    reason: str = "user_save",
    author_type: str = "user",
) -> ConceptPageRevision:
    current = db.scalar(
        select(func.max(ConceptPageRevision.revision_number)).where(
            ConceptPageRevision.page_id == page.id
        )
    )
    revision = ConceptPageRevision(
        page_id=page.id,
        revision_number=int(current or 0) + 1,
        snapshot_json=concept_snapshot(page),
        reason=reason,
        author_type=author_type,
    )
    db.add(revision)
    return revision


def add_lore_revision(
    db: Session,
    document: LoreDocument,
    *,
    reason: str,
    author_type: str = "user",
    body_markdown: str | None = None,
    body_json: dict[str, Any] | None = None,
) -> LoreRevision:
    current = db.scalar(
        select(func.max(LoreRevision.revision_number)).where(
            LoreRevision.document_id == document.id
        )
    )
    parent = db.scalar(
        select(LoreRevision.id)
        .where(LoreRevision.document_id == document.id)
        .order_by(LoreRevision.revision_number.desc())
        .limit(1)
    )
    revision = LoreRevision(
        document_id=document.id,
        parent_revision_id=parent,
        revision_number=int(current or 0) + 1,
        body_markdown=document.body_markdown if body_markdown is None else body_markdown,
        body_json=document.body_json if body_json is None else body_json,
        reason=reason,
        author_type=author_type,
    )
    db.add(revision)
    return revision
