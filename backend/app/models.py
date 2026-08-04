from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    universe_namespace: Mapped[str] = mapped_column(String(200), default="default")
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    concept_pages: Mapped[list["ConceptPage"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ConceptPage(Base, TimestampMixin):
    __tablename__ = "concept_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category_key: Mapped[str] = mapped_column(String(100), default="free", index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    usage_role: Mapped[str] = mapped_column(String(64), default="DRAFT_SETTING", index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    namespace: Mapped[str] = mapped_column(String(200), default="default", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    body_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    properties_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    locked_facts: Mapped[list[str]] = mapped_column(JSON, default=list)
    open_questions: Mapped[list[str]] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="concept_pages")


class ConceptRelation(Base, TimestampMixin):
    __tablename__ = "concept_relations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_page_id: Mapped[str] = mapped_column(ForeignKey("concept_pages.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_page_id: Mapped[str] = mapped_column(ForeignKey("concept_pages.id", ondelete="CASCADE"), index=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class DirectionCard(Base, TimestampMixin):
    __tablename__ = "direction_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    parsed_rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class WritingRecipe(Base, TimestampMixin):
    __tablename__ = "writing_recipes"
    __table_args__ = (UniqueConstraint("key", "version", name="uq_recipe_key_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    recipe_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)


class PlaybookSession(Base, TimestampMixin):
    __tablename__ = "playbook_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300), default="새 플레이북")
    concept_slots: Mapped[dict[str, list[str]]] = mapped_column(JSON, default=dict)
    direction_card_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    user_direction: Mapped[str] = mapped_column(Text, default="")
    writing_recipe_id: Mapped[str] = mapped_column(ForeignKey("writing_recipes.id"), index=True)
    output_profile: Mapped[str] = mapped_column(String(100), default="lore_article")
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    seed: Mapped[int] = mapped_column(default=0)
    state: Mapped[str] = mapped_column(String(32), default="draft")
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_pack_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class LoreDocument(Base, TimestampMixin):
    __tablename__ = "lore_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("playbook_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    writing_recipe_id: Mapped[str | None] = mapped_column(ForeignKey("writing_recipes.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, default="")
    body_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="draft")


class LoreRevision(Base, TimestampMixin):
    __tablename__ = "lore_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("lore_documents.id", ondelete="CASCADE"), index=True)
    parent_revision_id: Mapped[str | None] = mapped_column(ForeignKey("lore_revisions.id", ondelete="SET NULL"), nullable=True)
    body_markdown: Mapped[str] = mapped_column(Text, default="")
    body_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(String(300), default="generated")
    author_type: Mapped[str] = mapped_column(String(32), default="llm")


class GenerationRun(Base, TimestampMixin):
    __tablename__ = "generation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("playbook_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("lore_documents.id", ondelete="SET NULL"), nullable=True, index=True)
    task: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(300), default="")
    runtime: Mapped[str] = mapped_column(String(100), default="openai-compatible")
    prompt_components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    selected_concept_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    direction_card_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    input_hash: Mapped[str] = mapped_column(String(128), default="")
    output_text: Mapped[str] = mapped_column(Text, default="")


class ProposedConceptUpdate(Base, TimestampMixin):
    __tablename__ = "proposed_concept_updates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("lore_documents.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category_key: Mapped[str] = mapped_column(String(100), default="free")
    summary: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    source_excerpt: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
