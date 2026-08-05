from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.authority import AUTHORITY_STATES, canonical_role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=200)
    description: str = ""
    universe_namespace: str = "default"
    settings_json: dict[str, Any] = Field(default_factory=dict)


class ProjectRead(ORMModel):
    id: str
    name: str
    slug: str
    description: str
    universe_namespace: str
    settings_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    universe_namespace: str | None = None
    settings_json: dict[str, Any] | None = None


class CategoryDefinitionCreate(BaseModel):
    project_id: str | None = None
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    template_json: dict[str, Any] = Field(default_factory=dict)


class CategoryDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    template_json: dict[str, Any] | None = None


class CategoryDefinitionRead(ORMModel):
    id: str
    project_id: str | None
    key: str
    name: str
    description: str
    template_json: dict[str, Any]
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


class ConceptPageCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=300)
    category_key: str = "free"
    custom_category: str = ""
    tags: list[str] = Field(default_factory=list)
    usage_role: str = "DRAFT_SETTING"
    status: str = "active"
    namespace: str = "default"
    era: str = ""
    continuity: str = ""
    summary: str = ""
    body_json: dict[str, Any] = Field(default_factory=dict)
    properties_json: dict[str, Any] = Field(default_factory=dict)
    locked_facts: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    attachment_refs: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("usage_role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        return canonical_role(value)


class ConceptPageUpdate(BaseModel):
    title: str | None = None
    category_key: str | None = None
    custom_category: str | None = None
    tags: list[str] | None = None
    usage_role: str | None = None
    status: str | None = None
    namespace: str | None = None
    era: str | None = None
    continuity: str | None = None
    summary: str | None = None
    body_json: dict[str, Any] | None = None
    properties_json: dict[str, Any] | None = None
    locked_facts: list[str] | None = None
    open_questions: list[str] | None = None
    forbidden_changes: list[str] | None = None
    attachment_refs: list[dict[str, Any]] | None = None

    @field_validator("usage_role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        return canonical_role(value) if value is not None else None


class ConceptPageRead(ORMModel):
    id: str
    project_id: str
    title: str
    category_key: str
    custom_category: str
    tags: list[str]
    usage_role: str
    authority_state: str
    status: str
    namespace: str
    era: str
    continuity: str
    summary: str
    body_json: dict[str, Any]
    properties_json: dict[str, Any]
    locked_facts: list[str]
    open_questions: list[str]
    forbidden_changes: list[str]
    attachment_refs: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class DirectionCardCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    compatible_tags: list[str] = Field(default_factory=list)
    incompatible_tags: list[str] = Field(default_factory=list)
    parsed_rules: dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(default=1.0, ge=0)
    priority: int = 0
    enabled: bool = True


class DirectionCardRead(ORMModel):
    id: str
    project_id: str
    title: str
    body: str
    tags: list[str]
    compatible_tags: list[str]
    incompatible_tags: list[str]
    parsed_rules: dict[str, Any]
    weight: float
    priority: int
    enabled: bool
    use_count: int
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DirectionCardUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    tags: list[str] | None = None
    compatible_tags: list[str] | None = None
    incompatible_tags: list[str] | None = None
    parsed_rules: dict[str, Any] | None = None
    weight: float | None = Field(default=None, ge=0)
    priority: int | None = None
    enabled: bool | None = None


class ReferenceAnalysisRead(ORMModel):
    id: str
    project_id: str
    concept_page_id: str
    analysis_json: dict[str, Any]
    recipe_candidate_json: dict[str, Any]
    voice_candidate_json: dict[str, Any]
    similarity_report_json: dict[str, Any]
    status: str
    created_at: datetime


class ImageAnalysisRequest(BaseModel):
    image_data_url: str = Field(min_length=20)
    instruction: str = ""


class WritingRecipeRead(ORMModel):
    id: str
    project_id: str | None
    key: str
    version: str
    name: str
    description: str
    recipe_json: dict[str, Any]
    is_builtin: bool


class WritingRecipeCreate(BaseModel):
    project_id: str
    key: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=300)
    description: str = ""
    recipe_json: dict[str, Any] = Field(default_factory=dict)


class WritingRecipeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    recipe_json: dict[str, Any] | None = None
    approved: bool | None = None


class PlaybookSessionCreate(BaseModel):
    project_id: str
    name: str = "새 플레이북"
    concept_slots: dict[str, list[str]] = Field(default_factory=dict)
    direction_card_ids: list[str] = Field(default_factory=list)
    user_direction: str = ""
    writing_recipe_id: str
    output_profile: str = "lore_article"
    settings_json: dict[str, Any] = Field(default_factory=lambda: {
        "length": "normal",
        "detail_level": 3,
        "context_depth": "balanced",
        "creativity": "conservative",
    })
    seed: int = 0


class PlaybookSessionRead(ORMModel):
    id: str
    project_id: str
    name: str
    concept_slots: dict[str, list[str]]
    direction_card_ids: list[str]
    user_direction: str
    writing_recipe_id: str
    output_profile: str
    settings_json: dict[str, Any]
    seed: int
    state: str
    plan_json: dict[str, Any]
    evidence_pack_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PlaybookSessionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    concept_slots: dict[str, list[str]] | None = None
    direction_card_ids: list[str] | None = None
    user_direction: str | None = None
    writing_recipe_id: str | None = None
    output_profile: str | None = None
    settings_json: dict[str, Any] | None = None
    seed: int | None = None


class LoreDocumentUpdate(BaseModel):
    title: str | None = None
    body_markdown: str | None = None
    body_json: dict[str, Any] | None = None
    status: str | None = None


class LoreDocumentRead(ORMModel):
    id: str
    project_id: str
    session_id: str | None
    writing_recipe_id: str | None
    title: str
    body_markdown: str
    body_json: dict[str, Any]
    final_body_markdown: str
    finalized_from_hash: str
    finalized_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime


class FinalizationRequest(BaseModel):
    instruction: str = Field(default="", max_length=2000)


class FinalBodyUpdate(BaseModel):
    body_markdown: str = Field(min_length=1)


class FinalizationRead(BaseModel):
    document: LoreDocumentRead
    status: str
    draft_changed: bool
    current_draft_hash: str
    inputs: dict[str, Any]


class AuthorityPromotion(BaseModel):
    target_state: str
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("target_state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        if value not in AUTHORITY_STATES:
            raise ValueError("CANDIDATE, DRAFT_SETTING, PROJECT_CANON 중 하나여야 합니다.")
        return value


class ConceptRelationCreate(BaseModel):
    project_id: str
    source_page_id: str
    relation_type: str = Field(min_length=1, max_length=100)
    target_page_id: str
    notes: str = ""


class ConceptRelationRead(ORMModel):
    id: str
    project_id: str
    source_page_id: str
    relation_type: str
    target_page_id: str
    notes: str
    created_at: datetime


class CandidateCreate(BaseModel):
    project_id: str
    document_id: str
    target_page_id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    category_key: str = "free"
    candidate_sentence: str = ""
    summary: str = ""
    body: str = ""
    source_excerpt: str = ""
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    conflict_json: dict[str, Any] = Field(default_factory=dict)
    proposed_patch_json: dict[str, Any] = Field(default_factory=dict)


class CandidateDecision(BaseModel):
    decision: str
    reason: str = Field(min_length=1, max_length=1000)


class CandidateRead(ORMModel):
    id: str
    project_id: str
    document_id: str
    target_page_id: str | None
    approved_page_id: str | None
    title: str
    category_key: str
    candidate_sentence: str
    summary: str
    body: str
    source_excerpt: str
    evidence_json: dict[str, Any]
    conflict_json: dict[str, Any]
    proposed_patch_json: dict[str, Any]
    status: str
    created_at: datetime


class ReindexRequest(BaseModel):
    project_id: str
    concept_page_id: str | None = None


class IndexJobRead(ORMModel):
    id: str
    project_id: str
    concept_page_id: str | None
    action: str
    status: str
    attempt_count: int
    error_json: dict[str, Any]
    stats_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SearchRequest(BaseModel):
    project_id: str
    query: str = ""
    selected_page_ids: list[str] = Field(default_factory=list)
    namespaces: list[str] = Field(default_factory=list)
    source_roles: list[str] = Field(default_factory=list)
    factual_only: bool = True
    limit: int = Field(default=20, ge=1, le=100)


class PlanUpdate(BaseModel):
    plan_json: dict[str, Any]


class LoreBlockRead(ORMModel):
    id: str
    document_id: str
    position: int
    content_markdown: str
    content_json: dict[str, Any]
    rhetorical_move: str
    playbook_step: str
    evidence_ids: list[str]
    certainty: str
    source_role: str
    generation_run_id: str | None
    locked: bool
    candidate_claims: list[dict[str, Any]]
    audit_warnings: list[dict[str, Any]]
    updated_at: datetime


class LoreBlockUpdate(BaseModel):
    content_markdown: str | None = None
    position: int | None = None
    rhetorical_move: str | None = None
    evidence_ids: list[str] | None = None
    certainty: str | None = None
    locked: bool | None = None


class RewriteRequest(BaseModel):
    operation: str
    instruction: str = ""
    direction_card_ids: list[str] = Field(default_factory=list)
    voice_profile_id: str | None = None


class AuditFindingRead(ORMModel):
    id: str
    project_id: str
    document_id: str
    block_id: str | None
    audit_type: str
    severity: str
    code: str
    message: str
    evidence_json: dict[str, Any]
    proposed_diff: str
    status: str
    created_at: datetime


class GenerationResult(BaseModel):
    session: PlaybookSessionRead
    document: LoreDocumentRead | None = None
    plan: dict[str, Any] | None = None
    context_preview: dict[str, Any] | None = None
