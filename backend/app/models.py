from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.config import settings
from app.db import Base

APP_SCHEMA = "lore_app"
VECTOR_SCHEMA = "lore_vector"


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class EmbeddingVector(TypeDecorator[list[float]]):
    """Use pgvector in PostgreSQL and JSON in isolated SQLite tests."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(settings.embedding_dimension))
        return dialect.type_descriptor(JSON())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    universe_namespace: Mapped[str] = mapped_column(String(200), default="default", nullable=False)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    concept_pages: Mapped[list["ConceptPage"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    categories: Mapped[list["CategoryDefinition"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class CategoryDefinition(Base, TimestampMixin):
    __tablename__ = "category_definitions"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_category_project_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    template_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped[Project] = relationship(back_populates="categories")


class ConceptPage(Base, TimestampMixin):
    __tablename__ = "concept_pages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "category_key"],
            ["category_definitions.project_id", "category_definitions.key"],
            name="fk_concept_page_project_category",
            ondelete="RESTRICT",
        ),
        Index("ix_concept_project_namespace_role", "project_id", "namespace", "usage_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category_key: Mapped[str] = mapped_column(String(100), default="free", index=True, nullable=False)
    custom_category: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    usage_role: Mapped[str] = mapped_column(String(64), default="DRAFT_SETTING", index=True, nullable=False)
    authority_state: Mapped[str] = mapped_column(String(32), default="DRAFT_SETTING", index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True, nullable=False)
    namespace: Mapped[str] = mapped_column(String(200), default="default", index=True, nullable=False)
    era: Mapped[str] = mapped_column(String(200), default="", index=True, nullable=False)
    continuity: Mapped[str] = mapped_column(String(200), default="", index=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    properties_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    locked_facts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    open_questions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    forbidden_changes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    attachment_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    project: Mapped[Project] = relationship(back_populates="concept_pages")
    revisions: Mapped[list["ConceptPageRevision"]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )


class ConceptPageRevision(Base, TimestampMixin):
    __tablename__ = "concept_page_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    page_id: Mapped[str] = mapped_column(
        ForeignKey("concept_pages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), default="user_save", nullable=False)
    author_type: Mapped[str] = mapped_column(String(32), default="user", nullable=False)

    page: Mapped[ConceptPage] = relationship(back_populates="revisions")
    __table_args__ = (UniqueConstraint("page_id", "revision_number", name="uq_page_revision"),)


class ConceptRelation(Base, TimestampMixin):
    __tablename__ = "concept_relations"
    __table_args__ = (
        UniqueConstraint("project_id", "source_page_id", "relation_type", "target_page_id", name="uq_relation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_page_id: Mapped[str] = mapped_column(
        ForeignKey("concept_pages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_page_id: Mapped[str] = mapped_column(
        ForeignKey("concept_pages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class DirectionCard(Base, TimestampMixin):
    __tablename__ = "direction_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    compatible_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    incompatible_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    parsed_rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DirectionCardPool(Base, TimestampMixin):
    __tablename__ = "direction_card_pools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    card_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    filters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class WritingRecipe(Base, TimestampMixin):
    __tablename__ = "writing_recipes"
    __table_args__ = (UniqueConstraint("project_id", "key", "version", name="uq_recipe_project_key_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recipe_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class VoiceProfile(Base, TimestampMixin):
    __tablename__ = "voice_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class PlaybookSession(Base, TimestampMixin):
    __tablename__ = "playbook_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), default="새 플레이북", nullable=False)
    concept_slots: Mapped[dict[str, list[str]]] = mapped_column(JSON, default=dict, nullable=False)
    direction_card_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    user_direction: Mapped[str] = mapped_column(Text, default="", nullable=False)
    writing_recipe_id: Mapped[str] = mapped_column(ForeignKey("writing_recipes.id"), index=True, nullable=False)
    voice_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("voice_profiles.id", ondelete="SET NULL"), nullable=True
    )
    output_profile: Mapped[str] = mapped_column(String(100), default="lore_article", nullable=False)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    random_pool_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    locked_selections: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    evidence_pack_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class LoreDocument(Base, TimestampMixin):
    __tablename__ = "lore_documents"
    __table_args__ = (
        Index("ix_lore_documents_kind_project", "document_kind", "project_id"),
        Index(
            "ix_lore_documents_source_document_unique",
            "source_document_id",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("playbook_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    writing_recipe_id: Mapped[str | None] = mapped_column(
        ForeignKey("writing_recipes.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    document_kind: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("lore_documents.id", ondelete="CASCADE"), nullable=True
    )
    source_draft_hash: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    generation_inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)


class LoreRevision(Base, TimestampMixin):
    __tablename__ = "lore_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("lore_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parent_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("lore_revisions.id", ondelete="SET NULL"), nullable=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), default="generated", nullable=False)
    author_type: Mapped[str] = mapped_column(String(32), default="llm", nullable=False)


class LoreBlock(Base, TimestampMixin):
    __tablename__ = "lore_blocks"
    __table_args__ = (UniqueConstraint("document_id", "position", name="uq_document_block_position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("lore_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rhetorical_move: Mapped[str] = mapped_column(String(40), default="ANCHOR", nullable=False)
    playbook_step: Mapped[str] = mapped_column(String(64), default="DRAFT_BLOCKS", nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    certainty: Mapped[str] = mapped_column(String(32), default="INFERENCE", nullable=False)
    source_role: Mapped[str] = mapped_column(String(64), default="CANDIDATE", nullable=False)
    generation_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    candidate_claims: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    audit_warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)


class GenerationRun(Base, TimestampMixin):
    __tablename__ = "generation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("playbook_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("lore_documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task: Mapped[str] = mapped_column(String(64), nullable=False)
    model_role: Mapped[str] = mapped_column(String(32), default="writer", nullable=False)
    model: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, default="", nullable=False)
    runtime: Mapped[str] = mapped_column(String(100), default="openai-compatible", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    prompt_components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    selected_concept_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    direction_card_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    usage_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class GenerationStage(Base, TimestampMixin):
    __tablename__ = "generation_stages"
    __table_args__ = (UniqueConstraint("session_id", "step", "attempt", name="uq_generation_stage"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("playbook_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    generation_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    step: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AuditFinding(Base, TimestampMixin):
    __tablename__ = "audit_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("lore_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    block_id: Mapped[str | None] = mapped_column(
        ForeignKey("lore_blocks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    audit_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="warning", nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    proposed_diff: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", nullable=False)


class ProposedConceptUpdate(Base, TimestampMixin):
    __tablename__ = "proposed_concept_updates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("lore_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_page_id: Mapped[str | None] = mapped_column(
        ForeignKey("concept_pages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    approved_page_id: Mapped[str | None] = mapped_column(
        ForeignKey("concept_pages.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category_key: Mapped[str] = mapped_column(String(100), default="free", nullable=False)
    candidate_sentence: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    conflict_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    proposed_patch_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="CANDIDATE", index=True, nullable=False)


class ReferenceAnalysis(Base, TimestampMixin):
    __tablename__ = "reference_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    concept_page_id: Mapped[str] = mapped_column(
        ForeignKey("concept_pages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    analysis_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    recipe_candidate_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    voice_candidate_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    similarity_report_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="CANDIDATE", nullable=False)


class Attachment(Base, TimestampMixin):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    concept_page_id: Mapped[str | None] = mapped_column(
        ForeignKey("concept_pages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), default="reference", nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    external_uri: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    caption: Mapped[str] = mapped_column(Text, default="", nullable=False)


class EmbeddingChunk(Base, TimestampMixin):
    __tablename__ = "embedding_chunks"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "source_id",
            "chunk_hash",
            "embedding_model",
            "embedding_version",
            name="uq_embedding_chunk_version",
        ),
        Index("ix_embedding_scope", "project_id", "universe_namespace", "source_role"),
        {"schema": VECTOR_SCHEMA},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey(f"{APP_SCHEMA}.projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    concept_page_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{APP_SCHEMA}.concept_pages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    universe_namespace: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    source_role: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    index_scope: Mapped[str] = mapped_column(String(32), default="FACT", index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    search_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVector(), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(300), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(100), nullable=False)


class IndexJob(Base, TimestampMixin):
    __tablename__ = "index_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    concept_page_id: Mapped[str | None] = mapped_column(
        ForeignKey("concept_pages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(32), default="REINDEX", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    stats_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    before_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    after_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
