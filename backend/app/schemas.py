from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.authority import AUTHORITY_STATES, canonical_role
from app.services.writing_moves import canonicalize_recipe_json

VOICE_PROFILE_LIST_FIELDS = {
    "sentence_rhythm",
    "description_rules",
    "dialogue_rules",
    "figurative_language",
    "paragraph_rules",
    "avoid_patterns",
    "best_for",
    "audit_rules",
}
VOICE_PROFILE_FIELDS = {"reader_effect", "compatibility"} | VOICE_PROFILE_LIST_FIELDS
VOICE_SELECTION_MODES = {"model_default", "profile_default", "manual", "retrieved"}
VOICE_RIGHTS_BASES = {"SELF_AUTHORED", "LICENSED", "PUBLIC_DOMAIN", "ANALYSIS_ONLY"}
SAMPLING_PARAMETER_RANGES = {
    "temperature": (0.0, 2.0),
    "top_p": (0.01, 1.0),
    "top_k": (1, 200),
    "frequency_penalty": (-2.0, 2.0),
    "presence_penalty": (-2.0, 2.0),
}


def validate_generation_settings(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    result = dict(value)
    profile = str(result.get("sampling_profile", "balanced")).strip()
    if not profile or len(profile) > 80:
        raise ValueError("생성 성향 키가 올바르지 않습니다.")
    result["sampling_profile"] = profile
    overrides = result.get("sampling_overrides") or {}
    if not isinstance(overrides, dict):
        raise ValueError("샘플링 고급 설정은 객체여야 합니다.")
    unknown = set(overrides) - set(SAMPLING_PARAMETER_RANGES)
    if unknown:
        raise ValueError(f"지원하지 않는 샘플링 설정입니다: {', '.join(sorted(unknown))}")
    clean: dict[str, int | float | None] = {}
    for key, (minimum, maximum) in SAMPLING_PARAMETER_RANGES.items():
        raw = overrides.get(key)
        if raw is None:
            clean[key] = None
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"{key} 값은 숫자여야 합니다.")
        if not minimum <= raw <= maximum:
            raise ValueError(f"{key} 값은 {minimum}~{maximum} 범위여야 합니다.")
        clean[key] = int(raw) if key == "top_k" else float(raw)
    result["sampling_overrides"] = clean
    return result


def canonicalize_voice_profile_json(value: dict[str, Any]) -> dict[str, Any]:
    unknown = set(value) - VOICE_PROFILE_FIELDS
    if unknown:
        raise ValueError(f"지원하지 않는 문체 프로필 필드입니다: {', '.join(sorted(unknown))}")
    result: dict[str, Any] = {}
    reader_effect = value.get("reader_effect", "")
    if not isinstance(reader_effect, str):
        raise ValueError("reader_effect는 문자열이어야 합니다.")
    result["reader_effect"] = reader_effect.strip()
    for field in VOICE_PROFILE_LIST_FIELDS:
        raw = value.get(field, [])
        if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
            raise ValueError(f"{field}는 문자열 목록이어야 합니다.")
        result[field] = [item.strip() for item in raw if item.strip()]
    compatibility = value.get("compatibility", {})
    if not isinstance(compatibility, dict) or set(compatibility) - {
        "viewpoints",
        "tenses",
    }:
        raise ValueError("compatibility에는 viewpoints와 tenses만 사용할 수 있습니다.")
    normalized_compatibility: dict[str, list[str]] = {}
    for field in ("viewpoints", "tenses"):
        raw = compatibility.get(field, [])
        if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
            raise ValueError(f"compatibility.{field}는 문자열 목록이어야 합니다.")
        normalized_compatibility[field] = list(dict.fromkeys(item.strip() for item in raw if item.strip()))
    result["compatibility"] = normalized_compatibility
    return result


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    canon_policy: str | None = None
    cover_image: str = Field(default="", max_length=2_500_000)
    cover_image_name: str = Field(default="", max_length=300)

    @field_validator("cover_image")
    @classmethod
    def validate_cover_image(cls, value: str) -> str:
        if value and not value.startswith(
            (
                "data:image/jpeg;base64,",
                "data:image/png;base64,",
                "data:image/webp;base64,",
            )
        ):
            raise ValueError("프로젝트 커버는 JPEG, PNG, WebP 이미지여야 합니다.")
        return value


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=200)
    description: str = ""
    universe_namespace: str = "default"
    settings_json: ProjectSettings = Field(default_factory=ProjectSettings)


class ProjectRead(ORMModel):
    id: str
    name: str
    slug: str
    description: str
    universe_namespace: str
    settings_json: ProjectSettings
    created_at: datetime
    updated_at: datetime


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    universe_namespace: str | None = None
    settings_json: ProjectSettings | None = None


class CategoryDefinitionCreate(BaseModel):
    project_id: str
    key: str | None = Field(default=None, min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    template_json: dict[str, Any] = Field(default_factory=dict)


class CategoryDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    template_json: dict[str, Any] | None = None


class CategoryDefinitionRead(ORMModel):
    id: str
    project_id: str
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


class ConceptSeedRequest(BaseModel):
    project_id: str
    source_page_id: str
    category_key: str
    model_key: Literal["qwen", "gemma"]
    seed_count: int = Field(default=12, ge=6, le=30)
    additional_instruction: str = Field(default="", max_length=4000)


class ConceptSeedRead(BaseModel):
    seed_id: str
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=1200)


class ConceptSeedResponse(BaseModel):
    run_id: str
    source_page_id: str
    category_key: str
    model_key: Literal["qwen", "gemma"]
    seeds: list[ConceptSeedRead]


class ConceptBatchGenerateRequest(BaseModel):
    seed_run_id: str
    selected_seeds: list[ConceptSeedRead] = Field(min_length=1, max_length=10)

    @field_validator("selected_seeds")
    @classmethod
    def validate_unique_seed_ids(cls, value: list[ConceptSeedRead]) -> list[ConceptSeedRead]:
        ids = [item.seed_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("같은 씨앗을 두 번 선택할 수 없습니다.")
        return value


class ConceptBatchCandidateRead(BaseModel):
    run_id: str
    seed_id: str
    title: str
    summary: str
    content_text: str
    tags: list[str]
    warnings: list[str]


class ConceptBatchFailureRead(BaseModel):
    seed_id: str
    title: str
    code: str
    message: str


class ConceptBatchGenerateResponse(BaseModel):
    seed_run_id: str
    requested_count: int
    candidates: list[ConceptBatchCandidateRead]
    failures: list[ConceptBatchFailureRead]


class ConceptBatchCandidateAccept(BaseModel):
    run_id: str
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(default="", max_length=1600)
    content_text: str = Field(min_length=1, max_length=50_000)
    tags: list[str] = Field(default_factory=list, max_length=12)


class ConceptBatchAcceptRequest(BaseModel):
    seed_run_id: str
    candidates: list[ConceptBatchCandidateAccept] = Field(min_length=1, max_length=10)

    @field_validator("candidates")
    @classmethod
    def validate_unique_run_ids(
        cls, value: list[ConceptBatchCandidateAccept]
    ) -> list[ConceptBatchCandidateAccept]:
        ids = [item.run_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("같은 생성 결과를 두 번 저장할 수 없습니다.")
        return value


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


class ConceptBoundarySuggestionRequest(BaseModel):
    body_json: dict[str, Any] | None = Field(
        default=None,
        description="저장 전 편집 본문. 생략하면 저장된 본문을 사용한다.",
    )
    locked_facts: list[str] | None = None
    open_questions: list[str] | None = None
    forbidden_changes: list[str] | None = None


class WritingBoundarySuggestionItem(BaseModel):
    text: str = Field(min_length=1)
    source_excerpt: str = Field(min_length=1)


class WritingBoundarySuggestion(BaseModel):
    locked_facts: list[WritingBoundarySuggestionItem]
    open_questions: list[WritingBoundarySuggestionItem]
    forbidden_changes: list[WritingBoundarySuggestionItem]


class ConceptBoundarySuggestionRead(BaseModel):
    concept_page_id: str
    suggestion: WritingBoundarySuggestion
    persisted: bool = False


class ConceptAiRewriteRequest(BaseModel):
    body_json: dict[str, Any]
    model_key: Literal["qwen", "gemma"] = "gemma"
    # ProseMirror uses position 0 when an AllSelection starts at the document boundary.
    selection_from: int = Field(ge=0)
    selection_to: int = Field(ge=1)
    selection_text: str = Field(min_length=1, max_length=12_000)
    operation: Literal[
        "polish",
        "shorter",
        "longer",
        "clarify",
        "consistency",
        "custom",
    ] = "polish"
    instruction: str = Field(default="", max_length=2000)
    source_page_ids: list[str] = Field(default_factory=list, max_length=12)
    locked_facts: list[str] | None = None
    open_questions: list[str] | None = None
    forbidden_changes: list[str] | None = None

    @field_validator("selection_text")
    @classmethod
    def validate_selection_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("수정할 선택 영역에는 글자가 있어야 합니다.")
        return value

    @field_validator("source_page_ids")
    @classmethod
    def unique_source_page_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def custom_operation_requires_instruction(self) -> ConceptAiRewriteRequest:
        if self.operation == "custom" and not self.instruction.strip():
            raise ValueError("직접 지시 수정에는 추가 지시가 필요합니다.")
        return self


class ConceptAiDraftRequest(BaseModel):
    body_json: dict[str, Any]
    model_key: Literal["qwen", "gemma"] = "gemma"
    prompt: str = Field(min_length=1, max_length=4000)
    source_page_ids: list[str] = Field(default_factory=list, max_length=12)
    placement: Literal["replace", "cursor", "append"] = "replace"
    length: Literal["short", "normal", "long"] = "normal"
    locked_facts: list[str] | None = None
    open_questions: list[str] | None = None
    forbidden_changes: list[str] | None = None

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("AI 작성 지시를 입력해 주세요.")
        return value

    @field_validator("source_page_ids")
    @classmethod
    def unique_source_page_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class ConceptAiProposalRead(BaseModel):
    run_id: str
    concept_page_id: str
    mode: Literal["rewrite_selection", "draft"]
    model_key: Literal["qwen", "gemma"]
    status: Literal["CANDIDATE"] = "CANDIDATE"
    persisted: bool = False
    base_body_hash: str
    original_text: str = ""
    proposed_text: str
    selection_from: int | None = None
    selection_to: int | None = None
    source_page_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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
    key: str | None = Field(default=None, min_length=1, max_length=120)
    version: str = Field(default="1.0.0", min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=300)
    description: str = ""
    recipe_json: dict[str, Any]

    @field_validator("recipe_json")
    @classmethod
    def validate_recipe_json(cls, value: dict[str, Any]) -> dict[str, Any]:
        return canonicalize_recipe_json(value)


class WritingRecipeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    recipe_json: dict[str, Any] | None = None
    approved: bool | None = None

    @field_validator("recipe_json")
    @classmethod
    def validate_recipe_json(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        return WritingRecipeCreate.validate_recipe_json(value)


class VoiceProfileRead(ORMModel):
    id: str
    project_id: str | None
    key: str
    version: str
    name: str
    description: str
    profile_json: dict[str, Any]
    source_analysis_id: str | None
    is_builtin: bool
    status: Literal["DRAFT", "APPROVED", "DEPRECATED"]
    created_at: datetime
    updated_at: datetime


class VoiceProfileCreate(BaseModel):
    project_id: str | None = None
    key: str | None = Field(default=None, min_length=1, max_length=120)
    version: str = Field(default="1.0.0", min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=1000)
    profile_json: dict[str, Any]

    @field_validator("profile_json")
    @classmethod
    def validate_profile_json(cls, value: dict[str, Any]) -> dict[str, Any]:
        return canonicalize_voice_profile_json(value)


class VoiceProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=1000)
    profile_json: dict[str, Any] | None = None

    @field_validator("profile_json")
    @classmethod
    def validate_profile_json(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return canonicalize_voice_profile_json(value) if value is not None else None


class VoiceProfileDuplicateRequest(BaseModel):
    project_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=300)


class VoiceProfileExampleRead(ORMModel):
    id: str
    voice_profile_id: str
    source_concept_page_id: str | None
    label: str
    excerpt: str
    teaches_json: list[str]
    scene_tags: list[str]
    rights_basis: Literal["SELF_AUTHORED", "LICENSED", "PUBLIC_DOMAIN", "ANALYSIS_ONLY"]
    use_in_generation: bool
    position: int
    status: Literal["ACTIVE", "DISABLED", "REJECTED"]
    excerpt_hash: str
    created_at: datetime
    updated_at: datetime


class VoiceProfileExampleCreate(BaseModel):
    source_concept_page_id: str | None = None
    label: str = Field(min_length=1, max_length=300)
    excerpt: str = Field(min_length=1, max_length=12000)
    teaches_json: list[str] = Field(default_factory=list, max_length=12)
    scene_tags: list[str] = Field(default_factory=list, max_length=12)
    rights_basis: Literal["SELF_AUTHORED", "LICENSED", "PUBLIC_DOMAIN", "ANALYSIS_ONLY"] = "ANALYSIS_ONLY"
    use_in_generation: bool = False
    position: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def isolate_analysis_only(self) -> "VoiceProfileExampleCreate":
        self.teaches_json = list(dict.fromkeys(item.strip() for item in self.teaches_json if item.strip()))
        self.scene_tags = list(dict.fromkeys(item.strip() for item in self.scene_tags if item.strip()))
        if self.rights_basis == "ANALYSIS_ONLY":
            self.use_in_generation = False
        return self


class VoiceProfileExampleUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=300)
    excerpt: str | None = Field(default=None, min_length=1, max_length=12000)
    teaches_json: list[str] | None = Field(default=None, max_length=12)
    scene_tags: list[str] | None = Field(default=None, max_length=12)
    rights_basis: Literal["SELF_AUTHORED", "LICENSED", "PUBLIC_DOMAIN", "ANALYSIS_ONLY"] | None = None
    use_in_generation: bool | None = None
    position: int | None = Field(default=None, ge=0)
    status: Literal["ACTIVE", "DISABLED", "REJECTED"] | None = None


class ReferenceExampleRange(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    label: str = Field(default="참고 글 예시", min_length=1, max_length=300)
    teaches_json: list[str] = Field(default_factory=list, max_length=12)
    scene_tags: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_range(self) -> "ReferenceExampleRange":
        if self.end <= self.start:
            raise ValueError("예시 글 범위의 끝은 시작보다 커야 합니다.")
        return self


class ReferenceAnalysisApprovalRequest(BaseModel):
    approve_recipe: bool = True
    approve_voice_profile: bool = True
    voice_scope: Literal["PROJECT", "SHARED"] = "PROJECT"
    selected_voice_fields: list[str] = Field(default_factory=list)
    selected_example_ranges: list[ReferenceExampleRange] = Field(default_factory=list, max_length=5)
    rights_basis: Literal["SELF_AUTHORED", "LICENSED", "PUBLIC_DOMAIN", "ANALYSIS_ONLY"] = "ANALYSIS_ONLY"

    @field_validator("selected_voice_fields")
    @classmethod
    def validate_selected_voice_fields(cls, value: list[str]) -> list[str]:
        selected = list(dict.fromkeys(value))
        unknown = set(selected) - VOICE_PROFILE_FIELDS
        if unknown:
            raise ValueError(f"지원하지 않는 문체 분석 필드입니다: {', '.join(sorted(unknown))}")
        return selected

    @model_validator(mode="after")
    def require_selection(self) -> "ReferenceAnalysisApprovalRequest":
        if not self.approve_recipe and not self.approve_voice_profile:
            raise ValueError("전개 방식 또는 문체 프로필 중 하나 이상을 승인해야 합니다.")
        return self


class PlaybookSessionCreate(BaseModel):
    project_id: str
    name: str = "새 플레이북"
    concept_slots: dict[str, list[str]] = Field(default_factory=dict)
    direction_card_ids: list[str] = Field(default_factory=list)
    user_direction: str = ""
    writing_recipe_id: str
    voice_profile_id: str | None = None
    voice_selection_mode: Literal["model_default", "profile_default", "manual", "retrieved"] = "model_default"
    voice_example_ids: list[str] = Field(default_factory=list, max_length=5)
    output_profile: str = "lore_article"
    settings_json: dict[str, Any] = Field(
        default_factory=lambda: {
            "length": "normal",
            "detail_level": 3,
            "context_depth": "balanced",
            "creativity": "conservative",
        }
    )
    seed: int = 0

    @field_validator("settings_json")
    @classmethod
    def validate_settings(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_generation_settings(value) or {}

    @model_validator(mode="after")
    def validate_voice_selection(self) -> "PlaybookSessionCreate":
        self.voice_example_ids = list(dict.fromkeys(self.voice_example_ids))
        if self.voice_profile_id is None:
            if self.voice_example_ids:
                raise ValueError("문체 프로필 없이 예시 글만 선택할 수 없습니다.")
            self.voice_selection_mode = "model_default"
        elif self.voice_selection_mode == "model_default":
            self.voice_selection_mode = "profile_default"
        return self


class PlaybookSessionRead(ORMModel):
    id: str
    project_id: str
    name: str
    concept_slots: dict[str, list[str]]
    direction_card_ids: list[str]
    user_direction: str
    writing_recipe_id: str
    voice_profile_id: str | None
    voice_selection_mode: str
    voice_example_ids: list[str]
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
    voice_profile_id: str | None = None
    voice_selection_mode: Literal["model_default", "profile_default", "manual", "retrieved"] | None = None
    voice_example_ids: list[str] | None = Field(default=None, max_length=5)
    output_profile: str | None = None
    settings_json: dict[str, Any] | None = None
    seed: int | None = None

    @field_validator("settings_json")
    @classmethod
    def validate_settings(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_generation_settings(value)


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
    document_kind: str
    source_document_id: str | None
    source_draft_hash: str
    generation_inputs_json: dict[str, Any]
    published_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime


class FinalizationRefinement(BaseModel):
    priorities: list[Literal["coherence", "causality", "imagery", "rhythm", "deduplicate", "ending"]] = Field(
        default_factory=lambda: ["coherence", "deduplicate", "rhythm"],
        min_length=1,
        max_length=6,
    )
    intensity: Literal["light", "balanced", "strong"] = "balanced"
    length_policy: Literal["preserve", "tighten", "expand"] = "preserve"


class FinalizationRequest(BaseModel):
    instruction: str = Field(default="", max_length=2000)
    refinement: FinalizationRefinement = Field(default_factory=FinalizationRefinement)
    user_direction: str | None = Field(default=None, max_length=4000)
    writing_recipe_id: str | None = None
    voice_profile_id: str | None = None
    voice_selection_mode: Literal["model_default", "profile_default", "manual", "retrieved"] | None = None
    voice_example_ids: list[str] | None = Field(default=None, max_length=5)
    output_profile: str | None = None
    settings_json: dict[str, Any] | None = None


class LoreBookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=400)
    body_markdown: str = Field(min_length=1)
    status: str | None = None


class FinalizationRead(BaseModel):
    source_document: LoreDocumentRead
    lorebook_entry: LoreDocumentRead | None
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


class DraftBlockSave(BaseModel):
    id: str | None = None
    content_markdown: str = Field(min_length=1)
    rhetorical_move: str = "ANCHOR"
    evidence_ids: list[str] = Field(default_factory=list)
    certainty: str = "CANDIDATE"
    locked: bool = False


class DraftSaveRequest(BaseModel):
    title: str = Field(min_length=1, max_length=400)
    status: str = "draft"
    blocks: list[DraftBlockSave] = Field(min_length=1)


class DraftSaveRead(BaseModel):
    document: LoreDocumentRead
    blocks: list[LoreBlockRead]


class RewriteRequest(BaseModel):
    operation: str
    instruction: str = ""
    direction_card_ids: list[str] = Field(default_factory=list)
    voice_profile_id: str | None = None


class ProseAuditRequest(BaseModel):
    document_hash: str = Field(min_length=64, max_length=128)
    voice_profile_id: str | None = None
    voice_profile_version: str | None = Field(default=None, max_length=40)


class ProseRevisionRequest(BaseModel):
    finding_id: str
    document_hash: str = Field(min_length=64, max_length=128)
    instruction: str = Field(default="", max_length=2000)
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


class ProseAuditRead(BaseModel):
    document_id: str
    document_hash: str
    voice_profile_id: str | None
    voice_profile_version: str | None
    findings: list[AuditFindingRead]


class GenerationResult(BaseModel):
    session: PlaybookSessionRead
    document: LoreDocumentRead | None = None
    plan: dict[str, Any] | None = None
    context_preview: dict[str, Any] | None = None
