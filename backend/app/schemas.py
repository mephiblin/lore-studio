from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class ConceptPageCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=300)
    category_key: str = "free"
    tags: list[str] = Field(default_factory=list)
    usage_role: str = "DRAFT_SETTING"
    status: str = "active"
    namespace: str = "default"
    summary: str = ""
    body_json: dict[str, Any] = Field(default_factory=dict)
    properties_json: dict[str, Any] = Field(default_factory=dict)
    locked_facts: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ConceptPageUpdate(BaseModel):
    title: str | None = None
    category_key: str | None = None
    tags: list[str] | None = None
    usage_role: str | None = None
    status: str | None = None
    namespace: str | None = None
    summary: str | None = None
    body_json: dict[str, Any] | None = None
    properties_json: dict[str, Any] | None = None
    locked_facts: list[str] | None = None
    open_questions: list[str] | None = None


class ConceptPageRead(ORMModel):
    id: str
    project_id: str
    title: str
    category_key: str
    tags: list[str]
    usage_role: str
    status: str
    namespace: str
    summary: str
    body_json: dict[str, Any]
    properties_json: dict[str, Any]
    locked_facts: list[str]
    open_questions: list[str]
    created_at: datetime
    updated_at: datetime


class DirectionCardCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    parsed_rules: dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(default=1.0, ge=0)
    enabled: bool = True


class DirectionCardRead(ORMModel):
    id: str
    project_id: str
    title: str
    body: str
    tags: list[str]
    parsed_rules: dict[str, Any]
    weight: float
    enabled: bool
    created_at: datetime
    updated_at: datetime


class WritingRecipeRead(ORMModel):
    id: str
    project_id: str | None
    key: str
    version: str
    name: str
    description: str
    recipe_json: dict[str, Any]
    is_builtin: bool


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
    status: str
    created_at: datetime
    updated_at: datetime


class GenerationResult(BaseModel):
    session: PlaybookSessionRead
    document: LoreDocumentRead | None = None
    plan: dict[str, Any] | None = None
    context_preview: dict[str, Any] | None = None
