from __future__ import annotations

import difflib
import hashlib
import json
from typing import Any

import markdown
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    AuditFinding,
    AuditLog,
    CategoryDefinition,
    ConceptPage,
    ConceptRelation,
    DirectionCard,
    GenerationRun,
    GenerationStage,
    IndexJob,
    LoreBlock,
    LoreDocument,
    PlaybookSession,
    Project,
    ProposedConceptUpdate,
    ReferenceAnalysis,
    VoiceProfile,
    VoiceProfileExample,
    WritingRecipe,
    new_id,
)
from app.schemas import (
    VOICE_PROFILE_FIELDS,
    AuditFindingRead,
    AuthorityPromotion,
    CandidateCreate,
    CandidateDecision,
    CandidateRead,
    CategoryDefinitionCreate,
    CategoryDefinitionRead,
    CategoryDefinitionUpdate,
    ConceptAiDraftRequest,
    ConceptAiProposalRead,
    ConceptAiRewriteRequest,
    ConceptBatchAcceptRequest,
    ConceptBatchGenerateRequest,
    ConceptBatchGenerateResponse,
    ConceptBoundarySuggestionRead,
    ConceptBoundarySuggestionRequest,
    ConceptPageCreate,
    ConceptPageRead,
    ConceptPageUpdate,
    ConceptRelationCreate,
    ConceptRelationRead,
    ConceptSeedRequest,
    ConceptSeedResponse,
    DirectionCardCreate,
    DirectionCardRead,
    DirectionCardUpdate,
    DraftSaveRead,
    DraftSaveRequest,
    FinalizationRead,
    FinalizationRequest,
    GenerationResult,
    ImageAnalysisRequest,
    IndexJobRead,
    LoreBlockRead,
    LoreBlockUpdate,
    LoreBookUpdate,
    LoreDocumentRead,
    LoreDocumentUpdate,
    PlanUpdate,
    PlaybookSessionCreate,
    PlaybookSessionRead,
    PlaybookSessionUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    ProseAuditRead,
    ProseAuditRequest,
    ProseRevisionRequest,
    ReferenceAnalysisApprovalRequest,
    ReferenceAnalysisRead,
    ReindexRequest,
    RewriteRequest,
    SearchRequest,
    VoiceProfileCreate,
    VoiceProfileDuplicateRequest,
    VoiceProfileExampleCreate,
    VoiceProfileExampleRead,
    VoiceProfileExampleUpdate,
    VoiceProfileRead,
    VoiceProfileUpdate,
    WritingRecipeCreate,
    WritingRecipeRead,
    WritingRecipeUpdate,
    canonicalize_voice_profile_json,
)
from app.services.audits import prose_document_hash, run_prose_audits
from app.services.authority import (
    AUTHORITY_STATES,
    AuthorityTransitionError,
    promote_page,
)
from app.services.concept_ai import (
    ConceptAiError,
    body_hash,
    compile_concept_ai_context,
    concept_draft_context,
    draft_concept_body,
    rewrite_concept_selection,
)
from app.services.concept_batch import (
    BatchContext,
    ConceptBatchError,
    extract_candidate_quality,
    generate_selected_seeds,
    propose_seeds,
)
from app.services.config_loader import (
    load_direction_card_presets,
    load_output_profiles,
    load_page_templates,
    load_sampling_profiles,
    seed_project_categories,
)
from app.services.context_compiler import compile_context, tiptap_to_text
from app.services.harness import LoreHarness
from app.services.model_gateway import ModelGatewayError, local_text_profile
from app.services.revisions import add_concept_revision, add_lore_revision
from app.services.sampling import resolve_sampling_profile
from app.services.search import hybrid_search, index_stats, run_index_job
from app.services.utility_tools import (
    analyze_image,
    analyze_reference,
    audit_prose,
    extract_candidates,
    suggest_direction,
    suggest_writing_boundaries,
)
from app.services.writing_moves import MOVE_LABELS, canonicalize_recipe_json

router = APIRouter()
harness = LoreHarness()


def _get_or_404(db: Session, model: type[Any], object_id: str, label: str) -> Any:
    obj = db.get(model, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{label}을(를) 찾을 수 없습니다.")
    return obj


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _require_recipe_for_project(recipe: WritingRecipe, project_id: str) -> None:
    if not recipe.approved or recipe.project_id not in {None, project_id}:
        raise _error(
            422,
            "PROJECT_WRITING_RECIPE_REQUIRED",
            "현재 프로젝트의 전개 방식 또는 모든 프로젝트가 함께 쓰는 전개 방식만 선택할 수 있습니다.",
        )


def _require_voice_profile_for_project(
    profile: VoiceProfile,
    project_id: str,
    *,
    approved_only: bool = True,
) -> None:
    allowed_statuses = {"APPROVED"} if approved_only else {"DRAFT", "APPROVED", "DEPRECATED"}
    if profile.project_id not in {None, project_id} or profile.status not in allowed_statuses:
        raise _error(
            422,
            "PROJECT_VOICE_PROFILE_REQUIRED",
            "현재 프로젝트 또는 모든 프로젝트가 함께 쓰는 사용 가능한 문체 프로필만 선택할 수 있습니다.",
        )


def _next_voice_version(db: Session, profile: VoiceProfile) -> str:
    parts = profile.version.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
        candidate = ".".join(parts)
    except ValueError:
        candidate = f"{profile.version}.1"
    while db.scalar(
        select(VoiceProfile.id).where(
            VoiceProfile.project_id == profile.project_id,
            VoiceProfile.key == profile.key,
            VoiceProfile.version == candidate,
        )
    ):
        candidate = f"{candidate}.1"
    return candidate


def _json_contains(value: Any, needle: str) -> bool:
    if isinstance(value, dict):
        return any(_json_contains(item, needle) for item in value.values())
    if isinstance(value, list):
        return any(_json_contains(item, needle) for item in value)
    return value == needle


def _voice_profile_in_use(db: Session, profile: VoiceProfile) -> bool:
    if db.scalar(select(PlaybookSession.id).where(PlaybookSession.voice_profile_id == profile.id)):
        return True
    runs = db.scalars(
        select(GenerationRun).where(GenerationRun.project_id == profile.project_id)
        if profile.project_id
        else select(GenerationRun)
    )
    return any(_json_contains(run.input_json, profile.id) for run in runs)


def _clone_voice_version(
    db: Session,
    profile: VoiceProfile,
    *,
    changes: dict[str, Any] | None = None,
    key: str | None = None,
    project_id: str | None | object = ...,
) -> VoiceProfile:
    changes = changes or {}
    target_project_id = profile.project_id if project_id is ... else project_id
    version = "1.0.0" if key and key != profile.key else _next_voice_version(db, profile)
    clone = VoiceProfile(
        project_id=target_project_id,
        key=key or profile.key,
        version=version,
        name=changes.get("name", profile.name),
        description=changes.get("description", profile.description),
        profile_json=changes.get("profile_json", profile.profile_json),
        source_analysis_id=profile.source_analysis_id,
        is_builtin=False,
        status="DRAFT",
    )
    db.add(clone)
    db.flush()
    examples = db.scalars(
        select(VoiceProfileExample)
        .where(VoiceProfileExample.voice_profile_id == profile.id)
        .order_by(VoiceProfileExample.position, VoiceProfileExample.id)
    )
    for example in examples:
        db.add(
            VoiceProfileExample(
                voice_profile_id=clone.id,
                source_concept_page_id=(
                    example.source_concept_page_id if target_project_id == profile.project_id else None
                ),
                label=example.label,
                excerpt=example.excerpt,
                teaches_json=example.teaches_json,
                scene_tags=example.scene_tags,
                rights_basis=example.rights_basis,
                use_in_generation=example.use_in_generation,
                position=example.position,
                status=example.status,
                excerpt_hash=example.excerpt_hash,
            )
        )
    return clone


def _validate_voice_examples(
    db: Session,
    profile: VoiceProfile,
    example_ids: list[str],
) -> list[VoiceProfileExample]:
    unique_ids = list(dict.fromkeys(example_ids))
    if not unique_ids:
        return []
    examples = list(
        db.scalars(select(VoiceProfileExample).where(VoiceProfileExample.id.in_(unique_ids))).all()
    )
    by_id = {example.id: example for example in examples}
    if set(by_id) != set(unique_ids):
        raise _error(422, "VOICE_EXAMPLE_NOT_FOUND", "선택한 문체 예시를 찾을 수 없습니다.")
    ordered = [by_id[example_id] for example_id in unique_ids]
    if any(
        example.voice_profile_id != profile.id
        or example.status != "ACTIVE"
        or not example.use_in_generation
        or example.rights_basis == "ANALYSIS_ONLY"
        for example in ordered
    ):
        raise _error(
            422,
            "VOICE_EXAMPLE_NOT_AVAILABLE",
            "이 프로필에서 생성 입력으로 승인된 활성 예시만 선택할 수 있습니다.",
        )
    return ordered


def _apply_voice_selection(
    db: Session,
    *,
    project_id: str,
    profile_id: str | None,
    selection_mode: str,
    example_ids: list[str],
) -> None:
    if profile_id is None:
        if selection_mode != "model_default" or example_ids:
            raise _error(
                422,
                "VOICE_SELECTION_INVALID",
                "모델 기본 문체에는 별도 문체 예시를 연결할 수 없습니다.",
            )
        return
    profile = _get_or_404(db, VoiceProfile, profile_id, "문체 프로필")
    _require_voice_profile_for_project(profile, project_id)
    if selection_mode == "model_default":
        raise _error(422, "VOICE_SELECTION_INVALID", "문체 프로필 선택 방식을 확인해 주세요.")
    _validate_voice_examples(db, profile, example_ids)


def _recipe_json_with_identity(
    recipe_json: dict[str, Any], *, key: str, version: str, name: str, description: str
) -> dict[str, Any]:
    return {
        **recipe_json,
        "key": key,
        "version": version,
        "name": name,
        "description": description,
    }


def _normalize_reference_recipe(analysis: ReferenceAnalysis) -> dict[str, Any]:
    candidate = dict(analysis.recipe_candidate_json or {})
    allowed = set(MOVE_LABELS)
    required = [
        str(move).strip().upper()
        for move in candidate.get("required_moves", [])
        if str(move).strip().upper() in allowed
    ]
    if len(required) < 3:
        required = [
            str(item.get("primary_move", "")).strip().upper()
            for item in (analysis.analysis_json or {}).get("paragraphs", [])
            if str(item.get("primary_move", "")).strip().upper() in allowed
        ]
    for fallback in ("ORIENT", "ANCHOR", "INTERPRET"):
        if len(required) >= 3:
            break
        required.append(fallback)

    return canonicalize_recipe_json(
        {
            **candidate,
            "required_moves": required,
            "optional_moves": [
                str(move).strip().upper()
                for move in candidate.get("optional_moves", [])
                if str(move).strip().upper() in allowed and str(move).strip().upper() not in required
            ],
            "planner_rules": [str(rule) for rule in candidate.get("planner_rules", [])],
            "audit_rules": [str(rule) for rule in candidate.get("audit_rules", [])],
        }
    )


def _draft_document_or_404(db: Session, document_id: str) -> LoreDocument:
    document = _get_or_404(db, LoreDocument, document_id, "초안")
    if document.document_kind != "draft":
        raise _error(404, "DRAFT_NOT_FOUND", "편집 중인 초안을 찾을 수 없습니다.")
    return document


def _block_content_json(block: LoreBlock) -> dict[str, Any]:
    return {
        "type": "loreBlock",
        "attrs": {
            "id": block.id,
            "rhetoricalMove": block.rhetorical_move,
            "playbookStep": block.playbook_step,
            "evidenceIds": block.evidence_ids,
            "certainty": block.certainty,
            "sourceRole": block.source_role,
            "generationRun": block.generation_run_id,
            "locked": block.locked,
            "candidateClaims": block.candidate_claims,
            "auditWarnings": block.audit_warnings,
        },
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": block.content_markdown}],
            }
        ],
    }


def _sync_draft_document(document: LoreDocument, blocks: list[LoreBlock]) -> None:
    for block in blocks:
        block.content_json = _block_content_json(block)
    document.body_markdown = "\n\n".join(block.content_markdown for block in blocks)
    document.body_json = {
        "type": "doc",
        "content": [block.content_json for block in blocks],
    }


def _require_project(entity: Any, project_id: str, label: str) -> None:
    if entity.project_id != project_id:
        raise _error(
            404,
            "PROJECT_SCOPE_MISMATCH",
            f"이 프로젝트에서 {label}을(를) 찾을 수 없습니다.",
        )


def _resolve_category_key(
    db: Session,
    project_id: str,
    category_key: str,
    custom_category: str = "",
) -> str:
    """Validate a project category and upgrade the legacy custom-category input."""
    custom_name = custom_category.strip()
    if custom_name:
        category = db.scalar(
            select(CategoryDefinition).where(
                CategoryDefinition.project_id == project_id,
                CategoryDefinition.name == custom_name,
            )
        )
        if category is None:
            category = CategoryDefinition(
                project_id=project_id,
                key=f"custom-{new_id().replace('-', '')[:12]}",
                name=custom_name,
                description="기존 사용자 정의 종류에서 이전됨",
                template_json={},
                is_builtin=False,
            )
            db.add(category)
            db.flush()
        return category.key
    category = db.scalar(
        select(CategoryDefinition).where(
            CategoryDefinition.project_id == project_id,
            CategoryDefinition.key == category_key,
        )
    )
    if category is None:
        raise _error(
            422,
            "PROJECT_CATEGORY_REQUIRED",
            "현재 프로젝트에 속한 자료 종류를 선택해 주세요.",
        )
    return category.key


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/models/status")
async def model_status() -> dict[str, Any]:
    """Return model availability without exposing endpoints or credentials."""
    return {"mode": "live", "profiles": await harness.gateway.health_all()}


@router.get("/presets/page-templates")
def page_templates() -> list[dict[str, Any]]:
    return load_page_templates()


@router.get("/presets/output-profiles")
def output_profiles() -> list[dict[str, Any]]:
    return load_output_profiles()


@router.get("/presets/sampling-profiles")
def sampling_profiles() -> list[dict[str, Any]]:
    return load_sampling_profiles()


def _require_generation_presets(settings_json: dict[str, Any], output_profile: str) -> None:
    profile = next(
        (item for item in load_output_profiles() if item.get("key") == output_profile),
        None,
    )
    if profile is None:
        raise _error(422, "OUTPUT_PROFILE_NOT_FOUND", "선택한 결과물 종류를 찾을 수 없습니다.")
    try:
        resolve_sampling_profile(
            settings_json,
            recommended_key=profile.get("recommended_sampling_profile"),
        )
    except ValueError as exc:
        raise _error(422, "SAMPLING_PROFILE_NOT_FOUND", str(exc)) from exc


@router.get("/presets/direction-cards")
def direction_card_presets() -> list[dict[str, Any]]:
    return load_direction_card_presets()


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(**payload.model_dump())
    db.add(project)
    try:
        db.flush()
        seed_project_categories(db, project)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="같은 slug의 프로젝트가 이미 존재합니다.") from exc
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.updated_at.desc())).all())


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    return _get_or_404(db, Project, project_id, "프로젝트")


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)) -> Project:
    project = _get_or_404(db, Project, project_id, "프로젝트")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    project = _get_or_404(db, Project, project_id, "프로젝트")
    db.add(
        AuditLog(
            project_id=project.id,
            action="DELETE",
            entity_type="Project",
            entity_id=project.id,
            before_json={"name": project.name, "slug": project.slug},
            reason="사용자 명시 삭제",
        )
    )
    db.flush()
    # ConceptPage uses a project/category composite RESTRICT key so that a category
    # cannot be removed while in use. Remove the project's pages first; their own
    # revisions, relations, index jobs, and analyses still follow DB cascades.
    db.execute(delete(ConceptPage).where(ConceptPage.project_id == project_id))
    db.execute(delete(Project).where(Project.id == project_id))
    db.commit()


@router.post(
    "/categories",
    response_model=CategoryDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_category(payload: CategoryDefinitionCreate, db: Session = Depends(get_db)) -> CategoryDefinition:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    data = payload.model_dump()
    data["key"] = data.get("key") or f"custom-{new_id().replace('-', '')[:12]}"
    category = CategoryDefinition(**data, is_builtin=False)
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _error(409, "CATEGORY_KEY_EXISTS", "이 프로젝트에 같은 카테고리 키가 있습니다.") from exc
    db.refresh(category)
    return category


@router.get("/categories", response_model=list[CategoryDefinitionRead])
def list_categories(project_id: str = Query(...), db: Session = Depends(get_db)) -> list[CategoryDefinition]:
    _get_or_404(db, Project, project_id, "프로젝트")
    stmt = select(CategoryDefinition).where(CategoryDefinition.project_id == project_id)
    return list(db.scalars(stmt.order_by(CategoryDefinition.name)).all())


@router.patch("/categories/{category_id}", response_model=CategoryDefinitionRead)
def update_category(
    category_id: str, payload: CategoryDefinitionUpdate, db: Session = Depends(get_db)
) -> CategoryDefinition:
    category = _get_or_404(db, CategoryDefinition, category_id, "카테고리")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: str, db: Session = Depends(get_db)) -> None:
    category = _get_or_404(db, CategoryDefinition, category_id, "카테고리")
    page_count = (
        db.scalar(
            select(func.count(ConceptPage.id)).where(
                ConceptPage.project_id == category.project_id,
                ConceptPage.category_key == category.key,
            )
        )
        or 0
    )
    if page_count:
        raise _error(
            409,
            "CATEGORY_IN_USE",
            f"이 종류를 사용하는 자료가 {page_count}개 있습니다. 먼저 다른 종류로 옮겨 주세요.",
        )
    db.add(
        AuditLog(
            project_id=category.project_id,
            action="DELETE",
            entity_type="CategoryDefinition",
            entity_id=category.id,
            before_json={"key": category.key, "name": category.name},
            reason="사용자 명시 삭제",
        )
    )
    db.delete(category)
    db.commit()


@router.post(
    "/concept-pages",
    response_model=ConceptPageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_concept_page(payload: ConceptPageCreate, db: Session = Depends(get_db)) -> ConceptPage:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    data = payload.model_dump()
    data["category_key"] = _resolve_category_key(
        db,
        payload.project_id,
        payload.category_key,
        payload.custom_category,
    )
    page = ConceptPage(**data, authority_state=data["usage_role"])
    db.add(page)
    db.flush()
    add_concept_revision(db, page, reason="initial_create")
    db.add(IndexJob(project_id=page.project_id, concept_page_id=page.id, action="REINDEX"))
    db.commit()
    db.refresh(page)
    return page


@router.get("/concept-pages", response_model=list[ConceptPageRead])
def list_concept_pages(
    project_id: str = Query(...),
    usage_role: str | None = None,
    category_key: str | None = None,
    namespace: str | None = None,
    tag: str | None = None,
    query: str | None = None,
    related_to: str | None = None,
    relation_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[ConceptPage]:
    stmt = select(ConceptPage).where(ConceptPage.project_id == project_id)
    if usage_role:
        stmt = stmt.where(ConceptPage.usage_role == usage_role)
    if category_key:
        stmt = stmt.where(ConceptPage.category_key == category_key)
    if namespace:
        stmt = stmt.where(ConceptPage.namespace == namespace)
    if query:
        stmt = stmt.where(ConceptPage.title.ilike(f"%{query}%"))
    if related_to:
        relation_stmt = select(ConceptRelation).where(
            ConceptRelation.project_id == project_id,
            (ConceptRelation.source_page_id == related_to) | (ConceptRelation.target_page_id == related_to),
        )
        if relation_type:
            relation_stmt = relation_stmt.where(ConceptRelation.relation_type == relation_type)
        related_ids: set[str] = set()
        for relation in db.scalars(relation_stmt):
            related_ids.add(
                relation.target_page_id if relation.source_page_id == related_to else relation.source_page_id
            )
        stmt = stmt.where(ConceptPage.id.in_(related_ids or {"__no_related_page__"}))
    stmt = stmt.order_by(ConceptPage.updated_at.desc())
    pages = list(db.scalars(stmt).all())
    if tag:
        pages = [page for page in pages if tag in (page.tags or [])]
    return pages


def _batch_context(
    db: Session,
    *,
    source: ConceptPage,
    category: CategoryDefinition,
    additional_instruction: str,
) -> BatchContext:
    source_body = tiptap_to_text(source.body_json).strip()
    if not source_body:
        raise _error(
            422,
            "CONCEPT_BATCH_SOURCE_EMPTY",
            "참고할 세계관 자료의 본문을 먼저 작성해 주세요.",
        )
    if len(source_body) > 50_000:
        raise _error(
            422,
            "CONCEPT_BATCH_SOURCE_TOO_LONG",
            "자료 양산에 사용할 참고 본문은 5만 자 이하여야 합니다.",
        )
    existing_titles = list(
        db.scalars(
            select(ConceptPage.title)
            .where(
                ConceptPage.project_id == source.project_id,
                ConceptPage.category_key == category.key,
                ConceptPage.id != source.id,
            )
            .order_by(ConceptPage.updated_at.desc())
            .limit(80)
        ).all()
    )
    return BatchContext(
        project_id=source.project_id,
        source_page_id=source.id,
        source_title=source.title,
        source_summary=source.summary,
        source_body=source_body,
        source_boundaries={
            "locked_facts": list(source.locked_facts or []),
            "open_questions": list(source.open_questions or []),
            "forbidden_changes": list(source.forbidden_changes or []),
        },
        namespace=source.namespace,
        era=source.era,
        continuity=source.continuity,
        category_key=category.key,
        category_name=category.name,
        category_description=category.description,
        category_template=category.template_json or {},
        existing_titles=existing_titles,
        additional_instruction=additional_instruction.strip(),
    )


def _plain_text_to_tiptap(text: str) -> dict[str, Any]:
    paragraphs = [part.strip() for part in text.replace("\r\n", "\n").split("\n\n") if part.strip()]
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": paragraph}],
            }
            for paragraph in paragraphs
        ],
    }


@router.post("/concept-batches/seeds", response_model=ConceptSeedResponse)
async def create_concept_batch_seeds(
    payload: ConceptSeedRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    source = _get_or_404(db, ConceptPage, payload.source_page_id, "참고 세계관 자료")
    _require_project(source, payload.project_id, "참고 세계관 자료")
    if source.status == "rejected" or source.usage_role == "REJECTED":
        raise _error(
            422,
            "CONCEPT_BATCH_SOURCE_REJECTED",
            "폐기된 세계관 자료는 양산의 참고 자료로 사용할 수 없습니다.",
        )
    category = db.scalar(
        select(CategoryDefinition).where(
            CategoryDefinition.project_id == payload.project_id,
            CategoryDefinition.key == payload.category_key,
        )
    )
    if category is None:
        raise _error(
            404,
            "CONCEPT_BATCH_CATEGORY_NOT_FOUND",
            "선택한 자료 종류를 찾을 수 없습니다.",
        )
    context = _batch_context(
        db,
        source=source,
        category=category,
        additional_instruction=payload.additional_instruction,
    )
    profile = local_text_profile(payload.model_key)
    try:
        seeds, result = await propose_seeds(
            harness.gateway,
            profile=profile,
            context=context,
            seed_count=payload.seed_count,
        )
    except ConceptBatchError as exc:
        raise _error(exc.status_code, exc.code, str(exc)) from exc
    except ModelGatewayError as exc:
        raise _error(502, exc.code, str(exc)) from exc

    run = GenerationRun(
        project_id=payload.project_id,
        task="concept_batch_seed_planning",
        model_role=profile.role,
        model=result.model,
        endpoint=result.endpoint,
        status="completed",
        prompt_components={"concept_batch": "seed_planning_v2"},
        selected_concept_ids=[source.id],
        params_json=result.params,
        usage_json=result.usage,
        input_hash=body_hash(source.body_json),
        input_json={
            "model_key": payload.model_key,
            "seed_count": payload.seed_count,
            "context": context.to_json(),
        },
        output_text=result.content,
    )
    db.add(run)
    db.flush()
    response = {
        "run_id": run.id,
        "source_page_id": source.id,
        "category_key": category.key,
        "model_key": payload.model_key,
        "seeds": seeds,
    }
    db.commit()
    return response


@router.post("/concept-batches/generate", response_model=ConceptBatchGenerateResponse)
async def generate_concept_batch(
    payload: ConceptBatchGenerateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    seed_run = _get_or_404(db, GenerationRun, payload.seed_run_id, "씨앗 생성 기록")
    if seed_run.task != "concept_batch_seed_planning" or seed_run.status != "completed":
        raise _error(
            409,
            "CONCEPT_SEED_RUN_INVALID",
            "완료된 자료 씨앗 기록만 사용할 수 있습니다.",
        )
    seed_count = int(seed_run.input_json.get("seed_count", 0))
    valid_seed_ids = {f"seed-{index}" for index in range(1, seed_count + 1)}
    selected_seeds = [item.model_dump() for item in payload.selected_seeds]
    if any(seed["seed_id"] not in valid_seed_ids for seed in selected_seeds):
        raise _error(
            422,
            "CONCEPT_SEED_NOT_IN_RUN",
            "이 제안에 속하지 않은 씨앗이 포함되어 있습니다.",
        )
    try:
        context = BatchContext.from_json(seed_run.input_json.get("context", {}))
    except ConceptBatchError as exc:
        raise _error(exc.status_code, exc.code, str(exc)) from exc
    source = _get_or_404(db, ConceptPage, context.source_page_id, "참고 세계관 자료")
    _require_project(source, seed_run.project_id, "참고 세계관 자료")
    if source.status == "rejected" or source.usage_role == "REJECTED":
        raise _error(409, "CONCEPT_BATCH_SOURCE_REJECTED", "참고 세계관 자료가 폐기되었습니다.")
    category_exists = db.scalar(
        select(CategoryDefinition.id).where(
            CategoryDefinition.project_id == seed_run.project_id,
            CategoryDefinition.key == context.category_key,
        )
    )
    if category_exists is None:
        raise _error(409, "CONCEPT_BATCH_CATEGORY_REMOVED", "선택했던 자료 종류가 삭제되었습니다.")
    planner_model_key = seed_run.input_json.get("model_key")
    if planner_model_key not in {"qwen", "gemma"}:
        raise _error(
            409,
            "CONCEPT_SEED_RUN_INVALID",
            "씨앗 생성 기록의 모델 정보가 올바르지 않습니다.",
        )
    writer_model_key = payload.writer_model_key
    profile = local_text_profile(writer_model_key)
    results = await generate_selected_seeds(
        harness.gateway,
        profile=profile,
        context=context,
        seeds=selected_seeds,
        length_key=payload.length_key,
        max_concurrency=payload.max_concurrency,
    )

    candidates: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for seed, (candidate, result, error) in zip(selected_seeds, results, strict=True):
        if error is not None or candidate is None or result is None:
            code = getattr(error, "code", "CONCEPT_BATCH_WORKER_FAILED")
            message = str(error or "본문 생성 결과가 비어 있습니다.")
            run = GenerationRun(
                project_id=seed_run.project_id,
                task="concept_batch_worker",
                model_role=profile.role,
                model=profile.model,
                endpoint=profile.base_url,
                status="failed",
                prompt_components={"concept_batch": "candidate_writer_v2"},
                selected_concept_ids=[context.source_page_id],
                input_hash=seed_run.input_hash,
                input_json={
                    "seed_run_id": seed_run.id,
                    "source_page_id": context.source_page_id,
                    "category_key": context.category_key,
                    "planner_model_key": planner_model_key,
                    "writer_model_key": writer_model_key,
                    "length_key": payload.length_key,
                    "max_concurrency": payload.max_concurrency,
                    "seed": seed,
                },
                error_json={"code": code, "message": message},
            )
            db.add(run)
            db.flush()
            failures.append(
                {
                    "seed_id": seed["seed_id"],
                    "title": seed["title"],
                    "code": code,
                    "message": message,
                }
            )
            continue
        run = GenerationRun(
            project_id=seed_run.project_id,
            task="concept_batch_worker",
            model_role=profile.role,
            model=result.model,
            endpoint=result.endpoint,
            status="completed",
            prompt_components={"concept_batch": "candidate_writer_v2"},
            selected_concept_ids=[context.source_page_id],
            params_json=result.params,
            usage_json=result.usage,
            input_hash=seed_run.input_hash,
            input_json={
                "seed_run_id": seed_run.id,
                "source_page_id": context.source_page_id,
                "category_key": context.category_key,
                "planner_model_key": planner_model_key,
                "writer_model_key": writer_model_key,
                "length_key": payload.length_key,
                "max_concurrency": payload.max_concurrency,
                "seed": seed,
            },
            output_text=json.dumps(candidate, ensure_ascii=False),
        )
        db.add(run)
        db.flush()
        candidates.append({"run_id": run.id, **candidate})
    db.commit()
    return {
        "seed_run_id": seed_run.id,
        "requested_count": len(selected_seeds),
        "candidates": candidates,
        "failures": failures,
        "writer_model_key": writer_model_key,
        "length_key": payload.length_key,
        "max_concurrency": payload.max_concurrency,
    }


@router.post(
    "/concept-batches/accept",
    response_model=list[ConceptPageRead],
    status_code=status.HTTP_201_CREATED,
)
def accept_concept_batch(
    payload: ConceptBatchAcceptRequest,
    db: Session = Depends(get_db),
) -> list[ConceptPage]:
    seed_run = _get_or_404(db, GenerationRun, payload.seed_run_id, "씨앗 생성 기록")
    if seed_run.task != "concept_batch_seed_planning" or seed_run.status != "completed":
        raise _error(
            409,
            "CONCEPT_SEED_RUN_INVALID",
            "완료된 자료 씨앗 기록만 사용할 수 있습니다.",
        )
    try:
        context = BatchContext.from_json(seed_run.input_json.get("context", {}))
    except ConceptBatchError as exc:
        raise _error(exc.status_code, exc.code, str(exc)) from exc
    source = _get_or_404(db, ConceptPage, context.source_page_id, "참고 세계관 자료")
    _require_project(source, seed_run.project_id, "참고 세계관 자료")
    if source.status == "rejected" or source.usage_role == "REJECTED":
        raise _error(409, "CONCEPT_BATCH_SOURCE_REJECTED", "참고 세계관 자료가 폐기되었습니다.")
    category = db.scalar(
        select(CategoryDefinition).where(
            CategoryDefinition.project_id == seed_run.project_id,
            CategoryDefinition.key == context.category_key,
        )
    )
    if category is None:
        raise _error(
            409,
            "CONCEPT_BATCH_CATEGORY_REMOVED",
            "선택했던 자료 종류가 삭제되었습니다.",
        )

    run_ids = [item.run_id for item in payload.candidates]
    worker_runs = list(db.scalars(select(GenerationRun).where(GenerationRun.id.in_(run_ids))).all())
    runs_by_id = {run.id: run for run in worker_runs}
    invalid = [
        run_id
        for run_id in run_ids
        if run_id not in runs_by_id
        or runs_by_id[run_id].project_id != seed_run.project_id
        or runs_by_id[run_id].task != "concept_batch_worker"
        or runs_by_id[run_id].status != "completed"
        or runs_by_id[run_id].input_json.get("seed_run_id") != seed_run.id
    ]
    if invalid:
        raise _error(
            422,
            "CONCEPT_BATCH_RESULT_INVALID",
            "저장할 수 없는 생성 결과가 포함되어 있습니다.",
        )

    existing_pages = list(
        db.scalars(select(ConceptPage).where(ConceptPage.project_id == seed_run.project_id)).all()
    )
    accepted_run_ids = {
        str((page.properties_json or {}).get("batch_generation", {}).get("run_id", ""))
        for page in existing_pages
    }
    if accepted_run_ids.intersection(run_ids):
        raise _error(
            409,
            "CONCEPT_BATCH_ALREADY_ACCEPTED",
            "이미 저장한 생성 결과가 포함되어 있습니다.",
        )

    pages: list[ConceptPage] = []
    for item in payload.candidates:
        worker = runs_by_id[item.run_id]
        quality = extract_candidate_quality(worker.output_text or "")
        page = ConceptPage(
            project_id=seed_run.project_id,
            title=item.title.strip(),
            category_key=context.category_key,
            tags=list(dict.fromkeys(tag.strip() for tag in item.tags if tag.strip()))[:12],
            usage_role="CANDIDATE",
            authority_state="CANDIDATE",
            status="active",
            namespace=context.namespace,
            era=context.era,
            continuity=context.continuity,
            summary=item.summary.strip(),
            body_json=_plain_text_to_tiptap(item.content_text),
            properties_json={
                "batch_generation": {
                    "run_id": worker.id,
                    "seed_run_id": seed_run.id,
                    "seed_id": worker.input_json.get("seed", {}).get("seed_id", ""),
                    "source_page_id": context.source_page_id,
                    "planner_model_key": seed_run.input_json.get("model_key", ""),
                    "writer_model_key": worker.input_json.get("writer_model_key", ""),
                    "length_key": worker.input_json.get("length_key", "standard"),
                    "details": quality.get("details", []),
                    "inherited_facts": quality.get("inherited_facts", []),
                    "candidate_facts": quality.get("candidate_facts", []),
                    "warnings": quality.get("warnings", []),
                    "generated_character_count": quality.get("character_count", 0),
                    "character_count": len(item.content_text.strip()),
                }
            },
        )
        db.add(page)
        db.flush()
        add_concept_revision(db, page, reason="batch_candidate_accepted", author_type="ai")
        db.add(IndexJob(project_id=page.project_id, concept_page_id=page.id, action="REINDEX"))
        pages.append(page)
    batch_id = new_id()
    db.add(
        AuditLog(
            project_id=seed_run.project_id,
            action="CONCEPT_BATCH_ACCEPTED",
            entity_type="ConceptPageBatch",
            entity_id=batch_id,
            after_json={
                "page_ids": [page.id for page in pages],
                "source_page_id": context.source_page_id,
                "category_key": context.category_key,
                "seed_run_id": seed_run.id,
            },
            reason="사용자가 검토 후 선택한 AI 생성 후보 저장",
        )
    )
    db.commit()
    for page in pages:
        db.refresh(page)
    return pages


@router.get("/concept-pages/{page_id}", response_model=ConceptPageRead)
def get_concept_page(page_id: str, db: Session = Depends(get_db)) -> ConceptPage:
    return _get_or_404(db, ConceptPage, page_id, "컨셉 페이지")


@router.post(
    "/concept-pages/{page_id}/suggest-writing-boundaries",
    response_model=ConceptBoundarySuggestionRead,
)
async def suggest_concept_writing_boundaries(
    page_id: str,
    payload: ConceptBoundarySuggestionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    page = _get_or_404(db, ConceptPage, page_id, "컨셉 페이지")
    body_json = page.body_json if payload.body_json is None else payload.body_json
    body = tiptap_to_text(body_json).strip()
    if not body:
        raise _error(422, "CONCEPT_BODY_REQUIRED", "먼저 자료 본문을 작성해 주세요.")
    if len(body) > 50_000:
        raise _error(
            422,
            "CONCEPT_BODY_TOO_LONG",
            "AI 제안에 사용할 본문은 5만 자 이하여야 합니다.",
        )
    existing_boundaries = {
        "locked_facts": list(page.locked_facts or [])
        if payload.locked_facts is None
        else payload.locked_facts,
        "open_questions": list(page.open_questions or [])
        if payload.open_questions is None
        else payload.open_questions,
        "forbidden_changes": list(page.forbidden_changes or [])
        if payload.forbidden_changes is None
        else payload.forbidden_changes,
    }
    try:
        suggestion, result = await suggest_writing_boundaries(
            harness.gateway,
            title=page.title,
            body=body,
            existing_boundaries=existing_boundaries,
        )
    except (ModelGatewayError, ValueError) as exc:
        raise _error(
            502,
            getattr(exc, "code", "WRITING_BOUNDARY_SUGGESTION_FAILED"),
            str(exc),
        ) from exc
    db.add(
        GenerationRun(
            project_id=page.project_id,
            task="writing_boundary_suggestion",
            model_role="utility",
            model=result.model,
            endpoint=result.endpoint,
            params_json=result.params,
            usage_json=result.usage,
            input_json={
                "concept_page_id": page.id,
                "title": page.title,
                "body": body,
                "existing_boundaries": existing_boundaries,
            },
            prompt_components={"utility": "writing_boundary_extraction_v1"},
            selected_concept_ids=[page.id],
            output_text=result.content,
        )
    )
    db.commit()
    return {"concept_page_id": page.id, "suggestion": suggestion, "persisted": False}


@router.post(
    "/concept-pages/{page_id}/ai/rewrite-selection",
    response_model=ConceptAiProposalRead,
)
async def rewrite_concept_page_selection(
    page_id: str,
    payload: ConceptAiRewriteRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    page = _get_or_404(db, ConceptPage, page_id, "컨셉 페이지")
    profile = local_text_profile(payload.model_key)
    current_hash = body_hash(payload.body_json)
    context: dict[str, Any] = {}
    source_ids: list[str] = []
    if payload.selection_from >= payload.selection_to:
        raise _error(422, "INVALID_SELECTION", "수정할 본문 범위를 다시 선택해 주세요.")
    try:
        context, source_ids, body = compile_concept_ai_context(
            db,
            page,
            body_json=payload.body_json,
            source_page_ids=payload.source_page_ids,
            locked_facts=payload.locked_facts,
            open_questions=payload.open_questions,
            forbidden_changes=payload.forbidden_changes,
            selection_text=payload.selection_text,
        )
        if not body:
            raise ConceptAiError("CONCEPT_BODY_REQUIRED", "먼저 수정할 본문을 작성해 주세요.")
        if " ".join(payload.selection_text.split()) not in " ".join(body.split()):
            raise ConceptAiError(
                "SELECTION_NOT_IN_BODY",
                "선택한 문장이 현재 본문과 일치하지 않습니다. 다시 선택해 주세요.",
            )
        proposed_text, model_warnings, result = await rewrite_concept_selection(
            harness.gateway,
            profile=profile,
            context=context,
            selection_text=payload.selection_text,
            selection_from=payload.selection_from,
            selection_to=payload.selection_to,
            operation=payload.operation,
            instruction=payload.instruction,
        )
    except ConceptAiError as exc:
        if exc.result is not None:
            db.add(
                GenerationRun(
                    project_id=page.project_id,
                    task="concept_selection_rewrite",
                    model_role=exc.result.role,
                    model=exc.result.model,
                    endpoint=exc.result.endpoint,
                    status="failed",
                    params_json=exc.result.params,
                    usage_json=exc.result.usage,
                    input_hash=current_hash,
                    input_json={
                        "concept_page_id": page.id,
                        "body_json": payload.body_json,
                        "selection": {
                            "from": payload.selection_from,
                            "to": payload.selection_to,
                            "text": payload.selection_text,
                        },
                        "operation": payload.operation,
                        "model_key": payload.model_key,
                        "instruction": payload.instruction,
                        "context": context,
                    },
                    prompt_components={"concept_editor": "selection_contextual_rewrite_v3"},
                    selected_concept_ids=[page.id, *source_ids],
                    output_text=exc.result.content,
                    error_json={"code": exc.code, "message": str(exc)},
                )
            )
            db.commit()
        raise _error(exc.status_code, exc.code, str(exc)) from exc
    except ModelGatewayError as exc:
        raise _error(502, exc.code, str(exc)) from exc

    run = GenerationRun(
        project_id=page.project_id,
        task="concept_selection_rewrite",
        model_role=profile.role,
        model=result.model,
        endpoint=result.endpoint,
        params_json=result.params,
        usage_json=result.usage,
        input_hash=current_hash,
        input_json={
            "concept_page_id": page.id,
            "body_json": payload.body_json,
            "selection": {
                "from": payload.selection_from,
                "to": payload.selection_to,
                "text": payload.selection_text,
            },
            "operation": payload.operation,
            "model_key": payload.model_key,
            "instruction": payload.instruction,
            "context": context,
        },
        prompt_components={"concept_editor": "selection_contextual_rewrite_v3"},
        selected_concept_ids=[page.id, *source_ids],
        output_text=result.content,
    )
    db.add(run)
    db.commit()
    return {
        "run_id": run.id,
        "concept_page_id": page.id,
        "mode": "rewrite_selection",
        "model_key": payload.model_key,
        "base_body_hash": current_hash,
        "original_text": payload.selection_text,
        "proposed_text": proposed_text,
        "selection_from": payload.selection_from,
        "selection_to": payload.selection_to,
        "source_page_ids": source_ids,
        "warnings": [*context["warnings"], *model_warnings],
    }


@router.post(
    "/concept-pages/{page_id}/ai/draft",
    response_model=ConceptAiProposalRead,
)
async def draft_concept_page_body(
    page_id: str,
    payload: ConceptAiDraftRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    page = _get_or_404(db, ConceptPage, page_id, "컨셉 페이지")
    profile = local_text_profile(payload.model_key)
    current_hash = body_hash(payload.body_json)
    context: dict[str, Any] = {}
    source_ids: list[str] = []
    try:
        context, source_ids, _body = compile_concept_ai_context(
            db,
            page,
            body_json=payload.body_json,
            source_page_ids=payload.source_page_ids,
            locked_facts=payload.locked_facts,
            open_questions=payload.open_questions,
            forbidden_changes=payload.forbidden_changes,
        )
        context = concept_draft_context(context)
        proposed_text, model_warnings, result = await draft_concept_body(
            harness.gateway,
            profile=profile,
            context=context,
            prompt=payload.prompt,
            placement=payload.placement,
            length=payload.length,
        )
    except ConceptAiError as exc:
        if exc.result is not None:
            db.add(
                GenerationRun(
                    project_id=page.project_id,
                    task="concept_body_draft",
                    model_role=exc.result.role,
                    model=exc.result.model,
                    endpoint=exc.result.endpoint,
                    status="failed",
                    params_json=exc.result.params,
                    usage_json=exc.result.usage,
                    input_hash=current_hash,
                    input_json={
                        "concept_page_id": page.id,
                        "body_json": payload.body_json,
                        "prompt": payload.prompt,
                        "model_key": payload.model_key,
                        "placement": payload.placement,
                        "length": payload.length,
                        "context": context,
                    },
                    prompt_components={"concept_editor": "body_draft_v2"},
                    selected_concept_ids=[page.id, *source_ids],
                    output_text=exc.result.content,
                    error_json={"code": exc.code, "message": str(exc)},
                )
            )
            db.commit()
        raise _error(exc.status_code, exc.code, str(exc)) from exc
    except ModelGatewayError as exc:
        raise _error(502, exc.code, str(exc)) from exc

    run = GenerationRun(
        project_id=page.project_id,
        task="concept_body_draft",
        model_role=profile.role,
        model=result.model,
        endpoint=result.endpoint,
        params_json=result.params,
        usage_json=result.usage,
        input_hash=current_hash,
        input_json={
            "concept_page_id": page.id,
            "body_json": payload.body_json,
            "prompt": payload.prompt,
            "model_key": payload.model_key,
            "placement": payload.placement,
            "length": payload.length,
            "context": context,
        },
        prompt_components={"concept_editor": "body_draft_v2"},
        selected_concept_ids=[page.id, *source_ids],
        output_text=result.content,
    )
    db.add(run)
    db.commit()
    return {
        "run_id": run.id,
        "concept_page_id": page.id,
        "mode": "draft",
        "model_key": payload.model_key,
        "base_body_hash": current_hash,
        "proposed_text": proposed_text,
        "source_page_ids": source_ids,
        "warnings": [*context["warnings"], *model_warnings],
    }


@router.patch("/concept-pages/{page_id}", response_model=ConceptPageRead)
def update_concept_page(
    page_id: str,
    payload: ConceptPageUpdate,
    db: Session = Depends(get_db),
) -> ConceptPage:
    page = _get_or_404(db, ConceptPage, page_id, "컨셉 페이지")
    changes = payload.model_dump(exclude_unset=True)
    if "category_key" in changes or changes.get("custom_category"):
        changes["category_key"] = _resolve_category_key(
            db,
            page.project_id,
            str(changes.get("category_key", page.category_key)),
            str(changes.get("custom_category", "")),
        )
    requested_role = changes.get("usage_role")
    if requested_role in AUTHORITY_STATES and requested_role != page.authority_state:
        raise _error(
            409,
            "AUTHORITY_TRANSITION_REQUIRES_PROMOTION",
            "권위 상태 변경은 명시적 승격 API를 사용해야 합니다.",
        )
    for key, value in changes.items():
        setattr(page, key, value)
    if requested_role and requested_role not in AUTHORITY_STATES:
        page.authority_state = requested_role
    db.add(page)
    add_concept_revision(db, page)
    db.add(IndexJob(project_id=page.project_id, concept_page_id=page.id, action="REINDEX"))
    db.commit()
    db.refresh(page)
    return page


@router.delete("/concept-pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_concept_page(page_id: str, db: Session = Depends(get_db)) -> None:
    page = _get_or_404(db, ConceptPage, page_id, "컨셉 페이지")
    db.add(
        AuditLog(
            project_id=page.project_id,
            action="DELETE",
            entity_type="ConceptPage",
            entity_id=page.id,
            before_json={"title": page.title, "usage_role": page.usage_role},
            reason="사용자 명시 삭제",
        )
    )
    db.delete(page)
    db.commit()


@router.post("/concept-pages/{page_id}/promote", response_model=ConceptPageRead)
def promote_concept_page(
    page_id: str, payload: AuthorityPromotion, db: Session = Depends(get_db)
) -> ConceptPage:
    page = _get_or_404(db, ConceptPage, page_id, "컨셉 페이지")
    try:
        return promote_page(db, page, target_state=payload.target_state, reason=payload.reason)
    except AuthorityTransitionError as exc:
        raise _error(409, "INVALID_AUTHORITY_TRANSITION", str(exc)) from exc


@router.post(
    "/concept-relations",
    response_model=ConceptRelationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_relation(payload: ConceptRelationCreate, db: Session = Depends(get_db)) -> ConceptRelation:
    source = _get_or_404(db, ConceptPage, payload.source_page_id, "출발 페이지")
    target = _get_or_404(db, ConceptPage, payload.target_page_id, "대상 페이지")
    _require_project(source, payload.project_id, "출발 페이지")
    _require_project(target, payload.project_id, "대상 페이지")
    relation = ConceptRelation(**payload.model_dump())
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation


@router.get("/concept-pages/{page_id}/relations", response_model=list[ConceptRelationRead])
def list_relations(page_id: str, db: Session = Depends(get_db)) -> list[ConceptRelation]:
    _get_or_404(db, ConceptPage, page_id, "컨셉 페이지")
    return list(
        db.scalars(
            select(ConceptRelation)
            .where((ConceptRelation.source_page_id == page_id) | (ConceptRelation.target_page_id == page_id))
            .order_by(ConceptRelation.created_at)
        ).all()
    )


@router.delete("/concept-relations/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(relation_id: str, db: Session = Depends(get_db)) -> None:
    relation = _get_or_404(db, ConceptRelation, relation_id, "관계")
    db.delete(relation)
    db.commit()


@router.post("/concept-pages/{page_id}/analyze-image")
async def analyze_concept_image(
    page_id: str, payload: ImageAnalysisRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    page = _get_or_404(db, ConceptPage, page_id, "컨셉 페이지")
    if not payload.image_data_url.startswith("data:image/"):
        raise _error(
            422,
            "IMAGE_DATA_URL_REQUIRED",
            "브라우저에서 읽은 image data URL이 필요합니다.",
        )
    try:
        suggestion, result = await analyze_image(harness.gateway, payload.image_data_url, payload.instruction)
    except (ModelGatewayError, ValueError) as exc:
        raise _error(502, getattr(exc, "code", "VISION_ANALYSIS_FAILED"), str(exc)) from exc
    db.add(
        GenerationRun(
            project_id=page.project_id,
            task="vision_analysis",
            model_role="vision",
            model=result.model,
            endpoint=result.endpoint,
            params_json=result.params,
            usage_json=result.usage,
            input_json={"concept_page_id": page.id, "image_persisted": False},
            output_text=result.content,
        )
    )
    db.commit()
    return {"concept_page_id": page.id, "suggestion": suggestion, "persisted": False}


@router.post(
    "/direction-cards",
    response_model=DirectionCardRead,
    status_code=status.HTTP_201_CREATED,
)
def create_direction_card(payload: DirectionCardCreate, db: Session = Depends(get_db)) -> DirectionCard:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    card = DirectionCard(**payload.model_dump())
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.get("/direction-cards", response_model=list[DirectionCardRead])
def list_direction_cards(project_id: str = Query(...), db: Session = Depends(get_db)) -> list[DirectionCard]:
    return list(
        db.scalars(
            select(DirectionCard)
            .where(DirectionCard.project_id == project_id)
            .order_by(DirectionCard.updated_at.desc())
        ).all()
    )


@router.patch("/direction-cards/{card_id}", response_model=DirectionCardRead)
def update_direction_card(
    card_id: str, payload: DirectionCardUpdate, db: Session = Depends(get_db)
) -> DirectionCard:
    card = _get_or_404(db, DirectionCard, card_id, "집필 지침")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(card, key, value)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.delete("/direction-cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_direction_card(card_id: str, db: Session = Depends(get_db)) -> None:
    card = _get_or_404(db, DirectionCard, card_id, "집필 지침")
    db.delete(card)
    db.commit()


@router.post("/direction-cards/{card_id}/suggest-structure")
async def suggest_direction_structure(card_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    card = _get_or_404(db, DirectionCard, card_id, "집필 지침")
    try:
        suggestion, result = await suggest_direction(harness.gateway, card.body)
    except ModelGatewayError as exc:
        raise _error(502, exc.code, str(exc)) from exc
    db.add(
        GenerationRun(
            project_id=card.project_id,
            task="direction_structure",
            model_role="utility",
            model=result.model,
            endpoint=result.endpoint,
            params_json=result.params,
            usage_json=result.usage,
            input_json={"card_id": card.id, "original_body": card.body},
            output_text=result.content,
        )
    )
    db.commit()
    return {"card_id": card.id, "original_body": card.body, "suggestion": suggestion}


@router.get("/writing-recipes", response_model=list[WritingRecipeRead])
def list_writing_recipes(project_id: str | None = None, db: Session = Depends(get_db)) -> list[WritingRecipe]:
    stmt = select(WritingRecipe).where(WritingRecipe.approved.is_(True))
    if project_id:
        stmt = stmt.where((WritingRecipe.project_id == project_id) | (WritingRecipe.project_id.is_(None)))
    else:
        # The playbook's progression choices are global presets. Project recipes
        # created by reference analysis must never leak into another project.
        stmt = stmt.where(WritingRecipe.project_id.is_(None))
    rows = list(db.scalars(stmt.order_by(WritingRecipe.updated_at.desc())).all())
    latest: dict[tuple[str | None, str], WritingRecipe] = {}
    for recipe in rows:
        latest.setdefault((recipe.project_id, recipe.key), recipe)
    return sorted(latest.values(), key=lambda recipe: (recipe.name, recipe.version), reverse=False)


@router.post(
    "/writing-recipes",
    response_model=WritingRecipeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_writing_recipe(payload: WritingRecipeCreate, db: Session = Depends(get_db)) -> WritingRecipe:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    data = payload.model_dump()
    data["key"] = data.get("key") or f"custom-{new_id().replace('-', '')[:12]}"
    data["recipe_json"] = _recipe_json_with_identity(
        data["recipe_json"],
        key=data["key"],
        version=data["version"],
        name=data["name"],
        description=data["description"],
    )
    recipe = WritingRecipe(**data, is_builtin=False, approved=True)
    db.add(recipe)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _error(409, "RECIPE_VERSION_EXISTS", "같은 키와 버전의 집필 레시피가 있습니다.") from exc
    db.refresh(recipe)
    return recipe


@router.patch("/writing-recipes/{recipe_id}", response_model=WritingRecipeRead)
def update_writing_recipe(
    recipe_id: str, payload: WritingRecipeUpdate, db: Session = Depends(get_db)
) -> WritingRecipe:
    recipe = _get_or_404(db, WritingRecipe, recipe_id, "집필 레시피")
    if recipe.is_builtin:
        raise _error(409, "BUILTIN_RECIPE_IMMUTABLE", "기본 레시피는 수정할 수 없습니다.")
    changes = payload.model_dump(exclude_unset=True)
    in_use = db.scalar(select(PlaybookSession.id).where(PlaybookSession.writing_recipe_id == recipe.id))
    if in_use:
        parts = recipe.version.split(".")
        try:
            parts[-1] = str(int(parts[-1]) + 1)
            next_version = ".".join(parts)
        except ValueError:
            next_version = f"{recipe.version}.1"
        while db.scalar(
            select(WritingRecipe.id).where(
                WritingRecipe.project_id == recipe.project_id,
                WritingRecipe.key == recipe.key,
                WritingRecipe.version == next_version,
            )
        ):
            next_version = f"{next_version}.1"
        recipe = WritingRecipe(
            project_id=recipe.project_id,
            key=recipe.key,
            version=next_version,
            name=changes.get("name", recipe.name),
            description=changes.get("description", recipe.description),
            recipe_json=_recipe_json_with_identity(
                changes.get("recipe_json", recipe.recipe_json),
                key=recipe.key,
                version=next_version,
                name=changes.get("name", recipe.name),
                description=changes.get("description", recipe.description),
            ),
            approved=changes.get("approved", recipe.approved),
            is_builtin=False,
        )
        db.add(recipe)
    else:
        for key, value in changes.items():
            setattr(recipe, key, value)
        recipe.recipe_json = _recipe_json_with_identity(
            recipe.recipe_json,
            key=recipe.key,
            version=recipe.version,
            name=recipe.name,
            description=recipe.description,
        )
    db.commit()
    db.refresh(recipe)
    return recipe


@router.delete("/writing-recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_writing_recipe(recipe_id: str, db: Session = Depends(get_db)) -> None:
    recipe = _get_or_404(db, WritingRecipe, recipe_id, "집필 레시피")
    if recipe.is_builtin:
        raise _error(409, "BUILTIN_RECIPE_IMMUTABLE", "기본 레시피는 삭제할 수 없습니다.")
    if db.scalar(select(PlaybookSession.id).where(PlaybookSession.writing_recipe_id == recipe.id)):
        raise _error(
            409,
            "WRITING_RECIPE_IN_USE",
            "이 전개 방식을 사용한 글 만들기 기록이 있어 삭제할 수 없습니다.",
        )
    db.delete(recipe)
    db.commit()


@router.get("/voice-profiles", response_model=list[VoiceProfileRead])
def list_voice_profiles(
    project_id: str | None = None,
    profile_status: str | None = Query(default=None, alias="status"),
    include_deprecated: bool = False,
    db: Session = Depends(get_db),
) -> list[VoiceProfile]:
    stmt = select(VoiceProfile)
    if project_id:
        _get_or_404(db, Project, project_id, "프로젝트")
        stmt = stmt.where((VoiceProfile.project_id == project_id) | (VoiceProfile.project_id.is_(None)))
    else:
        stmt = stmt.where(VoiceProfile.project_id.is_(None))
    if profile_status:
        if profile_status not in {"DRAFT", "APPROVED", "DEPRECATED"}:
            raise _error(422, "VOICE_STATUS_INVALID", "문체 프로필 상태가 올바르지 않습니다.")
        stmt = stmt.where(VoiceProfile.status == profile_status)
    if not include_deprecated and profile_status != "DEPRECATED":
        stmt = stmt.where(VoiceProfile.status != "DEPRECATED")
    rows = list(db.scalars(stmt.order_by(VoiceProfile.updated_at.desc())).all())
    latest: dict[tuple[str | None, str], VoiceProfile] = {}
    for profile in rows:
        latest.setdefault((profile.project_id, profile.key), profile)
    return sorted(latest.values(), key=lambda item: (item.name, item.version))


@router.get("/voice-profiles/{profile_id}", response_model=VoiceProfileRead)
def get_voice_profile(
    profile_id: str,
    project_id: str | None = None,
    db: Session = Depends(get_db),
) -> VoiceProfile:
    profile = _get_or_404(db, VoiceProfile, profile_id, "문체 프로필")
    if profile.project_id is not None and profile.project_id != project_id:
        raise _error(404, "VOICE_PROFILE_NOT_FOUND", "문체 프로필을 찾을 수 없습니다.")
    return profile


@router.post(
    "/voice-profiles",
    response_model=VoiceProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def create_voice_profile(
    payload: VoiceProfileCreate,
    db: Session = Depends(get_db),
) -> VoiceProfile:
    if payload.project_id:
        _get_or_404(db, Project, payload.project_id, "프로젝트")
    if not payload.profile_json.get("reader_effect", "").strip():
        raise _error(422, "VOICE_READER_EFFECT_REQUIRED", "독자에게 남길 인상을 입력해 주세요.")
    data = payload.model_dump()
    data["key"] = data.get("key") or f"voice-{new_id().replace('-', '')[:12]}"
    if not data["description"]:
        data["description"] = data["profile_json"]["reader_effect"]
    profile = VoiceProfile(**data, is_builtin=False, status="DRAFT")
    db.add(profile)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _error(409, "VOICE_VERSION_EXISTS", "같은 키와 버전의 문체 프로필이 있습니다.") from exc
    db.refresh(profile)
    return profile


@router.patch("/voice-profiles/{profile_id}", response_model=VoiceProfileRead)
def update_voice_profile(
    profile_id: str,
    payload: VoiceProfileUpdate,
    db: Session = Depends(get_db),
) -> VoiceProfile:
    profile = _get_or_404(db, VoiceProfile, profile_id, "문체 프로필")
    if profile.is_builtin:
        raise _error(409, "BUILTIN_VOICE_IMMUTABLE", "기본 문체 프로필은 수정할 수 없습니다.")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return profile
    if "profile_json" in changes and not changes["profile_json"].get("reader_effect", "").strip():
        raise _error(422, "VOICE_READER_EFFECT_REQUIRED", "독자에게 남길 인상을 입력해 주세요.")
    before = {"id": profile.id, "version": profile.version, "status": profile.status}
    if profile.status != "DRAFT" or _voice_profile_in_use(db, profile):
        profile = _clone_voice_version(db, profile, changes=changes)
        action = "CREATE_VOICE_PROFILE_VERSION"
    else:
        for key, value in changes.items():
            setattr(profile, key, value)
        action = "UPDATE_VOICE_PROFILE"
    if not profile.description:
        profile.description = str(profile.profile_json.get("reader_effect", ""))
    db.add(profile)
    if profile.project_id:
        db.add(
            AuditLog(
                project_id=profile.project_id,
                action=action,
                entity_type="VoiceProfile",
                entity_id=profile.id,
                before_json=before,
                after_json={
                    "id": profile.id,
                    "version": profile.version,
                    "status": profile.status,
                },
                reason="사용자 문체 프로필 편집",
            )
        )
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/voice-profiles/{profile_id}/versions", response_model=VoiceProfileRead)
def create_voice_profile_version(
    profile_id: str,
    payload: VoiceProfileUpdate,
    db: Session = Depends(get_db),
) -> VoiceProfile:
    profile = _get_or_404(db, VoiceProfile, profile_id, "문체 프로필")
    if profile.is_builtin:
        raise _error(
            409,
            "BUILTIN_VOICE_IMMUTABLE",
            "기본 문체 프로필은 버전을 만들 수 없습니다.",
        )
    clone = _clone_voice_version(db, profile, changes=payload.model_dump(exclude_unset=True))
    if clone.project_id:
        db.add(
            AuditLog(
                project_id=clone.project_id,
                action="CREATE_VOICE_PROFILE_VERSION",
                entity_type="VoiceProfile",
                entity_id=clone.id,
                before_json={"id": profile.id, "version": profile.version},
                after_json={
                    "id": clone.id,
                    "version": clone.version,
                    "status": clone.status,
                },
                reason="사용자 새 문체 버전 생성",
            )
        )
    db.commit()
    db.refresh(clone)
    return clone


@router.post("/voice-profiles/{profile_id}/approve", response_model=VoiceProfileRead)
def approve_voice_profile(profile_id: str, db: Session = Depends(get_db)) -> VoiceProfile:
    profile = _get_or_404(db, VoiceProfile, profile_id, "문체 프로필")
    if profile.status != "DRAFT":
        raise _error(409, "VOICE_NOT_DRAFT", "검토 중인 문체 프로필만 승인할 수 있습니다.")
    if not str(profile.profile_json.get("reader_effect", "")).strip():
        raise _error(422, "VOICE_READER_EFFECT_REQUIRED", "독자에게 남길 인상을 입력해 주세요.")
    profile.status = "APPROVED"
    db.add(profile)
    if profile.project_id:
        db.add(
            AuditLog(
                project_id=profile.project_id,
                action="APPROVE_VOICE_PROFILE",
                entity_type="VoiceProfile",
                entity_id=profile.id,
                before_json={"status": "DRAFT"},
                after_json={"status": "APPROVED", "version": profile.version},
                reason="사용자 명시 승인",
            )
        )
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/voice-profiles/{profile_id}/deprecate", response_model=VoiceProfileRead)
def deprecate_voice_profile(profile_id: str, db: Session = Depends(get_db)) -> VoiceProfile:
    profile = _get_or_404(db, VoiceProfile, profile_id, "문체 프로필")
    if profile.is_builtin:
        raise _error(
            409,
            "BUILTIN_VOICE_IMMUTABLE",
            "기본 문체 프로필은 사용 중지할 수 없습니다.",
        )
    if profile.status != "APPROVED":
        raise _error(
            409,
            "VOICE_NOT_APPROVED",
            "사용 가능한 문체 프로필만 사용 중지할 수 있습니다.",
        )
    profile.status = "DEPRECATED"
    db.add(profile)
    if profile.project_id:
        db.add(
            AuditLog(
                project_id=profile.project_id,
                action="DEPRECATE_VOICE_PROFILE",
                entity_type="VoiceProfile",
                entity_id=profile.id,
                before_json={"status": "APPROVED"},
                after_json={"status": "DEPRECATED", "version": profile.version},
                reason="사용자 문체 프로필 사용 중지",
            )
        )
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/voice-profiles/{profile_id}/duplicate", response_model=VoiceProfileRead)
def duplicate_voice_profile(
    profile_id: str,
    payload: VoiceProfileDuplicateRequest,
    db: Session = Depends(get_db),
) -> VoiceProfile:
    profile = _get_or_404(db, VoiceProfile, profile_id, "문체 프로필")
    if payload.project_id:
        _get_or_404(db, Project, payload.project_id, "프로젝트")
    target_project_id = payload.project_id if "project_id" in payload.model_fields_set else profile.project_id
    clone = _clone_voice_version(
        db,
        profile,
        changes={"name": payload.name or f"{profile.name} 복사본"},
        key=f"voice-{new_id().replace('-', '')[:12]}",
        project_id=target_project_id,
    )
    db.commit()
    db.refresh(clone)
    return clone


@router.delete("/voice-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voice_profile(profile_id: str, db: Session = Depends(get_db)) -> None:
    profile = _get_or_404(db, VoiceProfile, profile_id, "문체 프로필")
    if profile.is_builtin:
        raise _error(409, "BUILTIN_VOICE_IMMUTABLE", "기본 문체 프로필은 삭제할 수 없습니다.")
    if _voice_profile_in_use(db, profile):
        raise _error(
            409,
            "PROFILE_IN_USE",
            "이 문체 프로필을 사용한 글 만들기 또는 생성 기록이 있어 삭제할 수 없습니다.",
        )
    project_id = profile.project_id
    profile_id_for_log = profile.id
    db.delete(profile)
    if project_id:
        db.add(
            AuditLog(
                project_id=project_id,
                action="DELETE_VOICE_PROFILE",
                entity_type="VoiceProfile",
                entity_id=profile_id_for_log,
                before_json={"version": profile.version, "status": profile.status},
                after_json={},
                reason="사용자 삭제",
            )
        )
    db.commit()


@router.get(
    "/voice-profiles/{profile_id}/examples",
    response_model=list[VoiceProfileExampleRead],
)
def list_voice_profile_examples(
    profile_id: str,
    db: Session = Depends(get_db),
) -> list[VoiceProfileExample]:
    _get_or_404(db, VoiceProfile, profile_id, "문체 프로필")
    return list(
        db.scalars(
            select(VoiceProfileExample)
            .where(VoiceProfileExample.voice_profile_id == profile_id)
            .order_by(VoiceProfileExample.position, VoiceProfileExample.id)
        ).all()
    )


@router.post(
    "/voice-profiles/{profile_id}/examples",
    response_model=VoiceProfileExampleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_voice_profile_example(
    profile_id: str,
    payload: VoiceProfileExampleCreate,
    db: Session = Depends(get_db),
) -> VoiceProfileExample:
    profile = _get_or_404(db, VoiceProfile, profile_id, "문체 프로필")
    if profile.status != "DRAFT" or profile.is_builtin:
        raise _error(409, "VOICE_VERSION_LOCKED", "새 DRAFT 버전에서 예시를 편집해 주세요.")
    if payload.source_concept_page_id:
        source = _get_or_404(db, ConceptPage, payload.source_concept_page_id, "참고 페이지")
        if profile.project_id is None or source.project_id != profile.project_id:
            raise _error(
                422,
                "VOICE_EXAMPLE_SCOPE_MISMATCH",
                "프로필 범위와 참고 페이지 프로젝트가 다릅니다.",
            )
        if source.usage_role != "DISCOURSE_REFERENCE":
            raise _error(
                422,
                "REFERENCE_ROLE_REQUIRED",
                "문체 참고 자료만 예시 출처로 연결할 수 있습니다.",
            )
    data = payload.model_dump()
    excerpt = data.pop("excerpt").strip()
    example = VoiceProfileExample(
        **data,
        excerpt=excerpt,
        voice_profile_id=profile.id,
        status="ACTIVE",
        excerpt_hash=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
    )
    db.add(example)
    db.commit()
    db.refresh(example)
    return example


@router.patch("/voice-profile-examples/{example_id}", response_model=VoiceProfileExampleRead)
def update_voice_profile_example(
    example_id: str,
    payload: VoiceProfileExampleUpdate,
    db: Session = Depends(get_db),
) -> VoiceProfileExample:
    example = _get_or_404(db, VoiceProfileExample, example_id, "문체 예시")
    profile = _get_or_404(db, VoiceProfile, example.voice_profile_id, "문체 프로필")
    if profile.status != "DRAFT" or profile.is_builtin:
        raise _error(409, "VOICE_VERSION_LOCKED", "새 DRAFT 버전에서 예시를 편집해 주세요.")
    changes = payload.model_dump(exclude_unset=True)
    rights = changes.get("rights_basis", example.rights_basis)
    if rights == "ANALYSIS_ONLY":
        changes["use_in_generation"] = False
    for key, value in changes.items():
        setattr(example, key, value)
    if "excerpt" in changes:
        example.excerpt = example.excerpt.strip()
        example.excerpt_hash = hashlib.sha256(example.excerpt.encode("utf-8")).hexdigest()
    db.add(example)
    db.commit()
    db.refresh(example)
    return example


@router.post(
    "/voice-profile-examples/{example_id}/toggle",
    response_model=VoiceProfileExampleRead,
)
def toggle_voice_profile_example(
    example_id: str,
    db: Session = Depends(get_db),
) -> VoiceProfileExample:
    example = _get_or_404(db, VoiceProfileExample, example_id, "문체 예시")
    profile = _get_or_404(db, VoiceProfile, example.voice_profile_id, "문체 프로필")
    if profile.status != "DRAFT" or profile.is_builtin:
        raise _error(409, "VOICE_VERSION_LOCKED", "새 DRAFT 버전에서 예시를 편집해 주세요.")
    if example.rights_basis == "ANALYSIS_ONLY":
        raise _error(
            422,
            "ANALYSIS_ONLY_EXAMPLE",
            "분석 전용 예시는 생성 입력에 사용할 수 없습니다.",
        )
    example.use_in_generation = not example.use_in_generation
    db.add(example)
    db.commit()
    db.refresh(example)
    return example


@router.delete("/voice-profile-examples/{example_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voice_profile_example(example_id: str, db: Session = Depends(get_db)) -> None:
    example = _get_or_404(db, VoiceProfileExample, example_id, "문체 예시")
    profile = _get_or_404(db, VoiceProfile, example.voice_profile_id, "문체 프로필")
    if profile.status != "DRAFT" or profile.is_builtin:
        raise _error(409, "VOICE_VERSION_LOCKED", "새 DRAFT 버전에서 예시를 편집해 주세요.")
    db.delete(example)
    db.commit()


@router.post(
    "/playbook-sessions",
    response_model=PlaybookSessionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_playbook_session(payload: PlaybookSessionCreate, db: Session = Depends(get_db)) -> PlaybookSession:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    recipe = _get_or_404(db, WritingRecipe, payload.writing_recipe_id, "전개 방식")
    _require_recipe_for_project(recipe, payload.project_id)
    _apply_voice_selection(
        db,
        project_id=payload.project_id,
        profile_id=payload.voice_profile_id,
        selection_mode=payload.voice_selection_mode,
        example_ids=payload.voice_example_ids,
    )
    _require_generation_presets(payload.settings_json, payload.output_profile)
    session = PlaybookSession(**payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/playbook-sessions", response_model=list[PlaybookSessionRead])
def list_playbook_sessions(
    project_id: str = Query(...), db: Session = Depends(get_db)
) -> list[PlaybookSession]:
    return list(
        db.scalars(
            select(PlaybookSession)
            .where(PlaybookSession.project_id == project_id)
            .order_by(PlaybookSession.updated_at.desc())
        ).all()
    )


@router.get("/playbook-sessions/{session_id}", response_model=PlaybookSessionRead)
def get_playbook_session(session_id: str, db: Session = Depends(get_db)) -> PlaybookSession:
    return _get_or_404(db, PlaybookSession, session_id, "플레이북 세션")


@router.patch("/playbook-sessions/{session_id}", response_model=PlaybookSessionRead)
def update_playbook_session(
    session_id: str, payload: PlaybookSessionUpdate, db: Session = Depends(get_db)
) -> PlaybookSession:
    session = _get_or_404(db, PlaybookSession, session_id, "플레이북 세션")
    changes = payload.model_dump(exclude_unset=True)
    if "writing_recipe_id" in changes:
        recipe = _get_or_404(db, WritingRecipe, changes["writing_recipe_id"], "전개 방식")
        _require_recipe_for_project(recipe, session.project_id)
    if "settings_json" in changes or "output_profile" in changes:
        _require_generation_presets(
            changes.get("settings_json", session.settings_json),
            changes.get("output_profile", session.output_profile),
        )
    voice_fields = {"voice_profile_id", "voice_selection_mode", "voice_example_ids"}
    if voice_fields & set(changes):
        profile_id = changes.get("voice_profile_id", session.voice_profile_id)
        if "voice_profile_id" in changes and "voice_example_ids" not in changes:
            changes["voice_example_ids"] = []
        example_ids = changes.get("voice_example_ids", session.voice_example_ids)
        selection_mode = changes.get("voice_selection_mode", session.voice_selection_mode)
        if profile_id is None:
            selection_mode = "model_default"
            example_ids = []
            changes["voice_selection_mode"] = selection_mode
            changes["voice_example_ids"] = example_ids
        elif selection_mode == "model_default":
            selection_mode = "profile_default"
            changes["voice_selection_mode"] = selection_mode
        _apply_voice_selection(
            db,
            project_id=session.project_id,
            profile_id=profile_id,
            selection_mode=selection_mode,
            example_ids=example_ids,
        )
    for key, value in changes.items():
        setattr(session, key, value)
    if changes:
        session.state = "draft"
    db.commit()
    db.refresh(session)
    return session


@router.delete("/playbook-sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playbook_session(session_id: str, db: Session = Depends(get_db)) -> None:
    session = _get_or_404(db, PlaybookSession, session_id, "플레이북 세션")
    db.delete(session)
    db.commit()


@router.patch("/playbook-sessions/{session_id}/plan", response_model=PlaybookSessionRead)
def update_session_plan(
    session_id: str, payload: PlanUpdate, db: Session = Depends(get_db)
) -> PlaybookSession:
    session = _get_or_404(db, PlaybookSession, session_id, "플레이북 세션")
    session.plan_json = payload.plan_json
    session.state = "plan_edited"
    db.add(session)
    current = db.scalar(
        select(func.max(GenerationStage.attempt)).where(
            GenerationStage.session_id == session.id,
            GenerationStage.step == "USER_EDITABLE_PLAN",
        )
    )
    db.add(
        GenerationStage(
            session_id=session.id,
            step="USER_EDITABLE_PLAN",
            attempt=int(current or 0) + 1,
            status="COMPLETED",
            input_json={"source": "user"},
            output_json=payload.plan_json,
        )
    )
    db.commit()
    db.refresh(session)
    return session


@router.post("/playbook-sessions/{session_id}/context-preview", response_model=GenerationResult)
def preview_context(session_id: str, db: Session = Depends(get_db)) -> GenerationResult:
    session = _get_or_404(db, PlaybookSession, session_id, "플레이북 세션")
    pack = harness.context_preview(db, session)
    return GenerationResult(session=session, context_preview=pack)


@router.post("/playbook-sessions/{session_id}/plan", response_model=GenerationResult)
async def plan_session(session_id: str, db: Session = Depends(get_db)) -> GenerationResult:
    session = _get_or_404(db, PlaybookSession, session_id, "플레이북 세션")
    plan = await harness.plan(db, session)
    return GenerationResult(session=session, plan=plan)


@router.post("/playbook-sessions/{session_id}/generate", response_model=GenerationResult)
async def generate_session(session_id: str, db: Session = Depends(get_db)) -> GenerationResult:
    session = _get_or_404(db, PlaybookSession, session_id, "플레이북 세션")
    document = await harness.generate(db, session)
    db.refresh(session)
    return GenerationResult(session=session, document=document, plan=session.plan_json)


@router.post("/playbook-sessions/{session_id}/generate/stream")
async def stream_generate_session(session_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    session = _get_or_404(db, PlaybookSession, session_id, "플레이북 세션")

    async def events():  # type: ignore[no-untyped-def]
        yield (
            "event: progress\ndata: "
            + json.dumps(
                {
                    "step": "DRAFT_BLOCKS",
                    "message": "Writer가 LoreBlock 원고를 작성하고 있습니다.",
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )
        try:
            document = await harness.generate(db, session)
            db.refresh(session)
            payload = GenerationResult(session=session, document=document, plan=session.plan_json)
            yield (
                "event: complete\ndata: " + json.dumps(jsonable_encoder(payload), ensure_ascii=False) + "\n\n"
            )
        except (ModelGatewayError, ValueError) as exc:
            yield (
                "event: error\ndata: "
                + json.dumps(
                    {
                        "code": getattr(exc, "code", "GENERATION_FAILED"),
                        "message": str(exc),
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/documents", response_model=list[LoreDocumentRead])
def list_documents(project_id: str = Query(...), db: Session = Depends(get_db)) -> list[LoreDocument]:
    return list(
        db.scalars(
            select(LoreDocument)
            .where(
                LoreDocument.project_id == project_id,
                LoreDocument.document_kind == "draft",
            )
            .order_by(LoreDocument.updated_at.desc())
        ).all()
    )


@router.get("/documents/{document_id}", response_model=LoreDocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)) -> LoreDocument:
    return _draft_document_or_404(db, document_id)


@router.patch("/documents/{document_id}", response_model=LoreDocumentRead)
def update_document(
    document_id: str,
    payload: LoreDocumentUpdate,
    db: Session = Depends(get_db),
) -> LoreDocument:
    document = _draft_document_or_404(db, document_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(document, key, value)
    db.add(document)
    add_lore_revision(db, document, reason="user_save")
    db.commit()
    db.refresh(document)
    return document


@router.patch("/documents/{document_id}/draft", response_model=DraftSaveRead)
def save_draft(
    document_id: str,
    payload: DraftSaveRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Save the editable title and the complete ordered block list as one revision."""
    document = _draft_document_or_404(db, document_id)
    existing = list(
        db.scalars(
            select(LoreBlock).where(LoreBlock.document_id == document_id).order_by(LoreBlock.position)
        ).all()
    )
    by_id = {block.id: block for block in existing}
    incoming_ids = [item.id for item in payload.blocks if item.id]
    if len(incoming_ids) != len(set(incoming_ids)):
        raise _error(422, "DUPLICATE_BLOCK", "같은 문단이 두 번 포함되어 있습니다.")
    unknown_ids = [block_id for block_id in incoming_ids if block_id not in by_id]
    if unknown_ids:
        raise _error(
            422,
            "BLOCK_SCOPE_MISMATCH",
            "이 초안에 속하지 않은 문단이 포함되어 있습니다.",
        )

    omitted = [block for block in existing if block.id not in incoming_ids]
    if any(block.locked for block in omitted):
        raise _error(409, "LOCKED_BLOCK_DELETE", "잠긴 문단은 잠금을 푼 뒤 삭제할 수 있습니다.")

    if not payload.title.strip():
        raise _error(422, "EMPTY_TITLE", "초안 제목을 입력해 주세요.")
    document.title = payload.title.strip()
    document.status = payload.status
    temporary_base = max((block.position for block in existing), default=0) + len(existing) + 1000
    saved_blocks: list[LoreBlock] = []
    for index, item in enumerate(payload.blocks):
        content = item.content_markdown
        if not content.strip():
            raise _error(422, "EMPTY_BLOCK", f"{index + 1}번 문단이 비어 있습니다.")
        block = by_id.get(item.id) if item.id else None
        if block is None:
            block = LoreBlock(
                document_id=document_id,
                position=temporary_base + index,
                content_markdown=content,
                rhetorical_move=item.rhetorical_move,
                evidence_ids=item.evidence_ids,
                certainty=item.certainty,
                source_role="CANDIDATE",
                locked=item.locked,
            )
            db.add(block)
        else:
            protected_change = any(
                (
                    block.content_markdown != content,
                    block.rhetorical_move != item.rhetorical_move,
                    block.evidence_ids != item.evidence_ids,
                    block.certainty != item.certainty,
                )
            )
            if block.locked and protected_change and item.locked:
                raise _error(409, "BLOCK_LOCKED", "잠긴 문단은 잠금을 푼 뒤 수정할 수 있습니다.")
            block.position = temporary_base + index
            block.content_markdown = content
            block.rhetorical_move = item.rhetorical_move
            block.evidence_ids = item.evidence_ids
            block.certainty = item.certainty
            block.locked = item.locked
            db.add(block)
        saved_blocks.append(block)

    for block in omitted:
        db.delete(block)
    db.flush()
    for index, block in enumerate(saved_blocks):
        block.position = index
    _sync_draft_document(document, saved_blocks)
    db.add(document)
    add_lore_revision(db, document, reason="user_draft_save", author_type="user")
    db.commit()
    db.refresh(document)
    for block in saved_blocks:
        db.refresh(block)
    return {"document": document, "blocks": saved_blocks}


@router.get("/documents/{document_id}/blocks", response_model=list[LoreBlockRead])
def list_document_blocks(document_id: str, db: Session = Depends(get_db)) -> list[LoreBlock]:
    _draft_document_or_404(db, document_id)
    return list(
        db.scalars(
            select(LoreBlock).where(LoreBlock.document_id == document_id).order_by(LoreBlock.position)
        ).all()
    )


@router.patch("/blocks/{block_id}", response_model=LoreBlockRead)
def update_block(block_id: str, payload: LoreBlockUpdate, db: Session = Depends(get_db)) -> LoreBlock:
    block = _get_or_404(db, LoreBlock, block_id, "LoreBlock")
    changes = payload.model_dump(exclude_unset=True)
    protected_changes = {
        key: value for key, value in changes.items() if key != "locked" and getattr(block, key) != value
    }
    if block.locked and protected_changes and changes.get("locked") is not False:
        raise _error(409, "BLOCK_LOCKED", "잠긴 문단은 내용을 변경할 수 없습니다.")
    for key, value in changes.items():
        setattr(block, key, value)
    document = _draft_document_or_404(db, block.document_id)
    blocks = list(
        db.scalars(
            select(LoreBlock).where(LoreBlock.document_id == document.id).order_by(LoreBlock.position)
        ).all()
    )
    _sync_draft_document(document, blocks)
    db.add_all([block, document])
    add_lore_revision(db, document, reason="user_block_save", author_type="user")
    db.commit()
    db.refresh(block)
    return block


@router.get("/documents/{document_id}/finalization", response_model=FinalizationRead)
def get_document_finalization(document_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    document = _draft_document_or_404(db, document_id)
    try:
        return harness.finalization_summary(db, document)
    except ValueError as exc:
        raise _error(409, "FINALIZATION_UNAVAILABLE", str(exc)) from exc


@router.post("/documents/{document_id}/finalize", response_model=FinalizationRead)
async def finalize_document(
    document_id: str,
    payload: FinalizationRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    document = _draft_document_or_404(db, document_id)
    voice_kwargs: dict[str, Any] = {}
    voice_fields = {"voice_profile_id", "voice_selection_mode", "voice_example_ids"}
    if voice_fields & payload.model_fields_set:
        profile_id = payload.voice_profile_id
        selection_mode = payload.voice_selection_mode or (
            "model_default" if profile_id is None else "profile_default"
        )
        example_ids = payload.voice_example_ids or []
        _apply_voice_selection(
            db,
            project_id=document.project_id,
            profile_id=profile_id,
            selection_mode=selection_mode,
            example_ids=example_ids,
        )
        voice_kwargs = {
            "voice_profile_id": profile_id,
            "voice_selection_mode": selection_mode,
            "voice_example_ids": example_ids,
        }
    try:
        return await harness.finalize_document(
            db,
            document,
            instruction=payload.instruction,
            refinement_json=payload.refinement.model_dump(),
            user_direction=payload.user_direction,
            writing_recipe_id=payload.writing_recipe_id,
            output_profile=payload.output_profile,
            settings_json=payload.settings_json,
            **voice_kwargs,
        )
    except ModelGatewayError as exc:
        raise _error(502, exc.code, str(exc)) from exc
    except ValueError as exc:
        raise _error(409, "FINALIZATION_FAILED", str(exc)) from exc


@router.get("/lorebook", response_model=list[LoreDocumentRead])
def list_lorebook(project_id: str = Query(...), db: Session = Depends(get_db)) -> list[LoreDocument]:
    return list(
        db.scalars(
            select(LoreDocument)
            .where(
                LoreDocument.project_id == project_id,
                LoreDocument.document_kind == "lorebook",
            )
            .order_by(LoreDocument.published_at.desc(), LoreDocument.updated_at.desc())
        ).all()
    )


@router.get("/lorebook/{entry_id}", response_model=LoreDocumentRead)
def get_lorebook_entry(entry_id: str, db: Session = Depends(get_db)) -> LoreDocument:
    entry = _get_or_404(db, LoreDocument, entry_id, "로어북 글")
    if entry.document_kind != "lorebook":
        raise _error(404, "LOREBOOK_ENTRY_NOT_FOUND", "로어북 글을 찾을 수 없습니다.")
    return entry


@router.patch("/lorebook/{entry_id}", response_model=LoreDocumentRead)
def update_lorebook_entry(
    entry_id: str,
    payload: LoreBookUpdate,
    db: Session = Depends(get_db),
) -> LoreDocument:
    entry = get_lorebook_entry(entry_id, db)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(entry, key, value.strip() if isinstance(value, str) else value)
    if "body_markdown" in changes:
        entry.body_json = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": paragraph}],
                }
                for paragraph in entry.body_markdown.split("\n\n")
                if paragraph.strip()
            ],
        }
    db.add(entry)
    add_lore_revision(db, entry, reason="lorebook_user_edit", author_type="user")
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/lorebook/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lorebook_entry(entry_id: str, db: Session = Depends(get_db)) -> None:
    entry = get_lorebook_entry(entry_id, db)
    db.add(
        AuditLog(
            project_id=entry.project_id,
            action="DELETE",
            entity_type="LoreDocument",
            entity_id=entry.id,
            before_json={
                "title": entry.title,
                "document_kind": entry.document_kind,
                "source_document_id": entry.source_document_id,
            },
            reason="사용자 명시 삭제",
        )
    )
    db.delete(entry)
    db.commit()


@router.post("/blocks/{block_id}/rewrite", response_model=AuditFindingRead)
async def propose_block_rewrite(
    block_id: str, payload: RewriteRequest, db: Session = Depends(get_db)
) -> AuditFinding:
    block = _get_or_404(db, LoreBlock, block_id, "LoreBlock")
    if block.locked:
        raise _error(409, "BLOCK_LOCKED", "잠긴 문단은 재작성할 수 없습니다.")
    document = _draft_document_or_404(db, block.document_id)
    session = _get_or_404(db, PlaybookSession, document.session_id, "플레이북 세션")
    operation_labels = {
        "shorter": "사실을 유지하며 더 짧게",
        "longer": "근거를 유지하며 더 자세하게",
        "add_example": "세계관 근거 안에서 구체적인 사례 추가",
        "expository": "설명형 문단으로 변경",
        "scene": "장면형 문단으로 변경",
        "style_only": "사실은 유지하고 문체만 변경",
        "transition": "앞뒤 연결만 자연스럽게 수정",
    }
    instruction = operation_labels.get(payload.operation, payload.operation)
    snapshot = document.generation_inputs_json or {}
    snapshot_voice = snapshot.get("voice_profile") or {}
    effective_voice_id = (
        payload.voice_profile_id
        if "voice_profile_id" in payload.model_fields_set
        else snapshot_voice.get("id", session.voice_profile_id)
    )
    effective_voice_mode = (
        "model_default"
        if effective_voice_id is None
        else snapshot.get("voice_selection_mode", session.voice_selection_mode or "profile_default")
    )
    effective_example_ids = [
        str(item.get("id"))
        for item in snapshot.get("style_examples", [])
        if isinstance(item, dict) and item.get("id")
    ]
    if "voice_profile_id" in payload.model_fields_set:
        effective_example_ids = []
        _apply_voice_selection(
            db,
            project_id=document.project_id,
            profile_id=effective_voice_id,
            selection_mode=effective_voice_mode,
            example_ids=effective_example_ids,
        )
    context_pack = compile_context(
        db,
        session,
        voice_profile_id=effective_voice_id,
        voice_selection_mode=effective_voice_mode,
        voice_example_ids=effective_example_ids,
    )
    ordered_blocks = list(
        db.scalars(
            select(LoreBlock).where(LoreBlock.document_id == document.id).order_by(LoreBlock.position)
        ).all()
    )
    block_index = next(index for index, item in enumerate(ordered_blocks) if item.id == block.id)
    rewrite_payload = {
        "task": instruction,
        "additional_instruction": payload.instruction,
        "target": block.content_markdown,
        "before": ordered_blocks[block_index - 1].content_markdown if block_index > 0 else "",
        "after": (
            ordered_blocks[block_index + 1].content_markdown if block_index + 1 < len(ordered_blocks) else ""
        ),
        "fact_boundaries": {
            "locked_facts": context_pack.get("locked_facts", []),
            "open_questions": context_pack.get("open_questions", []),
            "forbidden_material": context_pack.get("forbidden_material", []),
        },
        "expression_design": {
            "voice_profile": context_pack.get("voice_profile"),
            "style_examples": context_pack.get("style_examples", []),
            "fact_eligible": False,
        },
        "output_contract": "앞뒤 문맥을 읽되 target 범위를 대체할 한국어 문단만 출력한다.",
    }
    try:
        result = await harness.gateway.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "원고의 국소 수정자다. 전체 문맥을 먼저 파악한 뒤 지정된 문단만 고친다. "
                        "사실·고유명사·사건 순서를 보존하고 문체 예시의 내용은 사실로 사용하지 않는다. "
                        "설명 없이 대체 문단만 출력한다."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(rewrite_payload, ensure_ascii=False),
                },
            ],
            role="writer",
            temperature=0.45,
            max_tokens=min(8000, max(1200, len(block.content_markdown) * 2 + 400)),
            seed=session.seed,
        )
        proposed = result.content.strip()
    except ModelGatewayError as exc:
        raise _error(502, exc.code, str(exc)) from exc
    diff = "\n".join(
        difflib.unified_diff(
            block.content_markdown.splitlines(),
            proposed.splitlines(),
            fromfile="현재 문단",
            tofile="제안 문단",
            lineterm="",
        )
    )
    run = GenerationRun(
        project_id=document.project_id,
        session_id=session.id,
        document_id=document.id,
        task="rewrite",
        model_role="writer",
        model=result.model,
        endpoint=result.endpoint,
        params_json=result.params,
        usage_json=result.usage,
        prompt_components={
            "voice_profile_id": (context_pack.get("voice_profile") or {}).get("id"),
            "voice_profile_version": (context_pack.get("voice_profile") or {}).get("version"),
        },
        input_hash=hashlib.sha256(
            json.dumps(rewrite_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        input_json=rewrite_payload,
        output_text=proposed,
    )
    db.add(run)
    finding = AuditFinding(
        project_id=document.project_id,
        document_id=document.id,
        block_id=block.id,
        audit_type="REWRITE",
        severity="proposal",
        code="BLOCK_REWRITE_PROPOSAL",
        message="재작성 제안을 검토한 뒤 승인하거나 폐기하십시오.",
        evidence_json={
            "original": block.content_markdown,
            "proposed": proposed,
            "operation": payload.operation,
        },
        proposed_diff=diff,
        status="PENDING",
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@router.post("/documents/{document_id}/prose-audit", response_model=ProseAuditRead)
async def prose_audit_document(
    document_id: str,
    payload: ProseAuditRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    document = _draft_document_or_404(db, document_id)
    body = harness.draft_body(db, document)
    current_hash = prose_document_hash(body)
    if current_hash != payload.document_hash:
        raise _error(409, "DOCUMENT_CHANGED", "원고가 바뀌었습니다. 저장 후 다시 점검해 주세요.")
    snapshot_voice = (document.generation_inputs_json or {}).get("voice_profile") or {}
    profile_id = (
        payload.voice_profile_id
        if "voice_profile_id" in payload.model_fields_set
        else snapshot_voice.get("id")
    )
    profile: VoiceProfile | None = None
    if profile_id:
        profile = _get_or_404(db, VoiceProfile, profile_id, "문체 프로필")
        if profile.project_id not in {
            None,
            document.project_id,
        } or profile.status not in {
            "APPROVED",
            "DEPRECATED",
        }:
            raise _error(
                422,
                "PROJECT_VOICE_PROFILE_REQUIRED",
                "이 원고에서 사용할 수 없는 문체 프로필입니다.",
            )
        if payload.voice_profile_version and payload.voice_profile_version != profile.version:
            raise _error(
                409,
                "VOICE_VERSION_CHANGED",
                "문체 프로필 버전이 달라졌습니다. 다시 선택해 주세요.",
            )

    deterministic = run_prose_audits(db, document, voice_profile=profile)
    blocks = list(
        db.scalars(
            select(LoreBlock).where(LoreBlock.document_id == document.id).order_by(LoreBlock.position)
        ).all()
    )
    audit_input = {
        "blocks": [{"id": block.id, "body": block.content_markdown} for block in blocks],
        "voice_profile": profile.profile_json if profile else None,
        "deterministic_findings": [
            {"block_id": item.block_id, "category": item.code, "reason": item.message}
            for item in deterministic
        ],
    }
    try:
        model_audit, result = await audit_prose(
            harness.gateway,
            blocks=audit_input["blocks"],
            voice_profile=audit_input["voice_profile"],
            deterministic_findings=audit_input["deterministic_findings"],
        )
    except ModelGatewayError as exc:
        model_audit = {"issues": [], "strengths": [], "uncertainties": [str(exc)]}
        result = None

    known_blocks = {block.id for block in blocks}
    existing_pairs = {(item.block_id, item.code) for item in deterministic}
    model_findings: list[AuditFinding] = []
    for issue in model_audit.get("issues", []):
        block_id = str(issue.get("block_id", ""))
        category = str(issue.get("category", "PROFILE_CONFLICT"))
        if block_id not in known_blocks or (block_id, category) in existing_pairs:
            continue
        finding = AuditFinding(
            project_id=document.project_id,
            document_id=document.id,
            block_id=block_id,
            audit_type="PROSE",
            severity=str(issue.get("severity", "info")),
            code=category,
            message=str(issue.get("reason", "문체 표현을 검토해 주세요.")),
            evidence_json={
                "start_text": issue.get("start_text", ""),
                "profile_rule": issue.get("profile_rule", ""),
                "source": "utility",
            },
            status="PENDING",
        )
        db.add(finding)
        model_findings.append(finding)
    if result:
        db.add(
            GenerationRun(
                project_id=document.project_id,
                session_id=document.session_id,
                document_id=document.id,
                task="prose_audit",
                model_role="utility",
                model=result.model,
                endpoint=result.endpoint,
                params_json=result.params,
                usage_json=result.usage,
                prompt_components={
                    "voice_profile_id": profile.id if profile else None,
                    "voice_profile_version": profile.version if profile else None,
                },
                input_hash=hashlib.sha256(
                    json.dumps(audit_input, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                input_json=audit_input,
                output_text=result.content,
            )
        )
    db.commit()
    findings = list(
        db.scalars(
            select(AuditFinding)
            .where(
                AuditFinding.document_id == document.id,
                AuditFinding.audit_type == "PROSE",
                AuditFinding.status == "PENDING",
            )
            .order_by(AuditFinding.created_at.desc())
        ).all()
    )
    return {
        "document_id": document.id,
        "document_hash": current_hash,
        "voice_profile_id": profile.id if profile else None,
        "voice_profile_version": profile.version if profile else None,
        "findings": findings,
    }


@router.post("/documents/{document_id}/prose-revision", response_model=AuditFindingRead)
async def propose_prose_revision(
    document_id: str,
    payload: ProseRevisionRequest,
    db: Session = Depends(get_db),
) -> AuditFinding:
    document = _draft_document_or_404(db, document_id)
    current_hash = prose_document_hash(harness.draft_body(db, document))
    if current_hash != payload.document_hash:
        raise _error(409, "DOCUMENT_CHANGED", "원고가 바뀌었습니다. 저장 후 다시 제안해 주세요.")
    source = _get_or_404(db, AuditFinding, payload.finding_id, "필력 점검 항목")
    if source.document_id != document.id or source.audit_type != "PROSE" or not source.block_id:
        raise _error(
            422,
            "PROSE_FINDING_NOT_REVISABLE",
            "문단에 연결된 필력 점검 항목만 수정 제안으로 만들 수 있습니다.",
        )
    rewrite_payload = RewriteRequest(
        operation="style_only",
        instruction=f"{source.message} {payload.instruction}".strip(),
    )
    if "voice_profile_id" in payload.model_fields_set:
        rewrite_payload = RewriteRequest(
            operation="style_only",
            instruction=rewrite_payload.instruction,
            voice_profile_id=payload.voice_profile_id,
        )
    proposal = await propose_block_rewrite(source.block_id, rewrite_payload, db)
    proposal.evidence_json = {**proposal.evidence_json, "source_audit_id": source.id}
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


@router.get("/documents/{document_id}/audits", response_model=list[AuditFindingRead])
def list_audits(document_id: str, db: Session = Depends(get_db)) -> list[AuditFinding]:
    _draft_document_or_404(db, document_id)
    return list(
        db.scalars(
            select(AuditFinding)
            .where(AuditFinding.document_id == document_id)
            .order_by(AuditFinding.created_at.desc())
        ).all()
    )


@router.post("/audits/{finding_id}/apply", response_model=AuditFindingRead)
def apply_finding(finding_id: str, db: Session = Depends(get_db)) -> AuditFinding:
    finding = _get_or_404(db, AuditFinding, finding_id, "수정 제안")
    if finding.status != "PENDING" or finding.audit_type != "REWRITE":
        raise _error(409, "FINDING_NOT_APPLICABLE", "적용 가능한 재작성 제안이 아닙니다.")
    block = _get_or_404(db, LoreBlock, finding.block_id, "LoreBlock")
    if block.locked:
        raise _error(409, "BLOCK_LOCKED", "잠긴 문단에는 제안을 적용할 수 없습니다.")
    block.content_markdown = str(finding.evidence_json.get("proposed", ""))
    finding.status = "APPLIED"
    document = _draft_document_or_404(db, block.document_id)
    blocks = list(
        db.scalars(
            select(LoreBlock).where(LoreBlock.document_id == document.id).order_by(LoreBlock.position)
        ).all()
    )
    _sync_draft_document(document, blocks)
    db.add_all([block, finding, document])
    add_lore_revision(db, document, reason="approved_block_rewrite")
    db.commit()
    db.refresh(finding)
    return finding


@router.post("/audits/{finding_id}/dismiss", response_model=AuditFindingRead)
def dismiss_finding(finding_id: str, db: Session = Depends(get_db)) -> AuditFinding:
    finding = _get_or_404(db, AuditFinding, finding_id, "감사 경고")
    finding.status = "DISMISSED"
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@router.get("/documents/{document_id}/export")
def export_document(
    document_id: str,
    format: str = Query(default="markdown", pattern="^(markdown|html|json)$"),
    include_metadata: bool = False,
    db: Session = Depends(get_db),
) -> Response:
    document = _draft_document_or_404(db, document_id)
    blocks = list(
        db.scalars(
            select(LoreBlock).where(LoreBlock.document_id == document.id).order_by(LoreBlock.position)
        ).all()
    )
    draft_body = "\n\n".join(item.content_markdown for item in blocks) or document.body_markdown
    if format == "markdown":
        value = draft_body
        if include_metadata:
            value += (
                "\n\n<!-- lore-studio: "
                + json.dumps(
                    [
                        {
                            "id": item.id,
                            "move": item.rhetorical_move,
                            "evidence": item.evidence_ids,
                        }
                        for item in blocks
                    ],
                    ensure_ascii=False,
                )
                + " -->"
            )
        return Response(value, media_type="text/markdown; charset=utf-8")
    if format == "html":
        value = markdown.markdown(draft_body, extensions=["extra"])
        return Response(value, media_type="text/html; charset=utf-8")
    value = {
        "document": LoreDocumentRead.model_validate(document).model_dump(mode="json"),
        "blocks": [LoreBlockRead.model_validate(item).model_dump(mode="json") for item in blocks],
        "exported_version": "draft",
        "exported_body_markdown": draft_body,
    }
    return Response(json.dumps(value, ensure_ascii=False), media_type="application/json")


@router.get("/lorebook/{entry_id}/export")
def export_lorebook_entry(
    entry_id: str,
    format: str = Query(default="markdown", pattern="^(markdown|html|json)$"),
    db: Session = Depends(get_db),
) -> Response:
    entry = get_lorebook_entry(entry_id, db)
    if format == "markdown":
        return Response(entry.body_markdown, media_type="text/markdown; charset=utf-8")
    if format == "html":
        return Response(
            markdown.markdown(entry.body_markdown, extensions=["extra"]),
            media_type="text/html; charset=utf-8",
        )
    value = {
        "lorebook_entry": LoreDocumentRead.model_validate(entry).model_dump(mode="json"),
        "source_document_id": entry.source_document_id,
        "generation_inputs": entry.generation_inputs_json,
    }
    return Response(json.dumps(value, ensure_ascii=False), media_type="application/json")


@router.get("/documents/{document_id}/video-beats")
def export_video_beats(document_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    document = _draft_document_or_404(db, document_id)
    blocks = list(
        db.scalars(
            select(LoreBlock).where(LoreBlock.document_id == document.id).order_by(LoreBlock.position)
        ).all()
    )
    beats = []
    cursor = 0.0
    for block in blocks:
        estimated = max(1.0, len(block.content_markdown.replace(" ", "")) / 5.5)
        beats.append(
            {
                "block_id": block.id,
                "rhetorical_move": block.rhetorical_move,
                "narration": block.content_markdown,
                "visual_beat": f"{block.rhetorical_move} 의미를 보여주는 세계관 내부 장면",
                "sound_cue": "",
                "generation_constraint": "고유 설정의 외형을 임의로 확정하지 않음",
                "comfyui_prompt_draft": f"cinematic lore illustration, {block.rhetorical_move.lower()}, no text",
                "start_seconds": round(cursor, 2),
                "estimated_duration_seconds": round(estimated, 2),
                "duration_source": "character_estimate",
            }
        )
        cursor += estimated
    return {
        "document_id": document.id,
        "title": document.title,
        "estimated_total_seconds": round(cursor, 2),
        "tts_configured": False,
        "beats": beats,
    }


@router.post("/candidates", response_model=CandidateRead, status_code=status.HTTP_201_CREATED)
def create_candidate(payload: CandidateCreate, db: Session = Depends(get_db)) -> ProposedConceptUpdate:
    document = _draft_document_or_404(db, payload.document_id)
    _require_project(document, payload.project_id, "로어 문서")
    if payload.target_page_id:
        target = _get_or_404(db, ConceptPage, payload.target_page_id, "기존 컨셉 페이지")
        _require_project(target, payload.project_id, "기존 컨셉 페이지")
    data = payload.model_dump()
    data["category_key"] = _resolve_category_key(db, payload.project_id, payload.category_key)
    candidate = ProposedConceptUpdate(**data, status="CANDIDATE")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.post("/documents/{document_id}/extract-candidates", response_model=list[CandidateRead])
async def extract_document_candidates(
    document_id: str, db: Session = Depends(get_db)
) -> list[ProposedConceptUpdate]:
    document = _draft_document_or_404(db, document_id)
    session = db.get(PlaybookSession, document.session_id) if document.session_id else None
    if session:
        pack = compile_context(db, session)
        known_pages = [
            {
                "id": item["id"],
                "title": item["title"],
                "summary": item.get("summary", ""),
            }
            for item in pack.get("selected_concepts", [])
        ]
    else:
        pages = db.scalars(select(ConceptPage).where(ConceptPage.project_id == document.project_id)).all()
        known_pages = [{"id": page.id, "title": page.title, "summary": page.summary} for page in pages]
    categories = [
        {"key": category.key, "name": category.name}
        for category in db.scalars(
            select(CategoryDefinition)
            .where(CategoryDefinition.project_id == document.project_id)
            .order_by(CategoryDefinition.name)
        ).all()
    ]
    try:
        data, result = await extract_candidates(
            harness.gateway,
            body=harness.draft_body(db, document),
            known_pages=known_pages,
            categories=categories,
        )
    except ModelGatewayError as exc:
        raise _error(502, exc.code, str(exc)) from exc
    created: list[ProposedConceptUpdate] = []
    category_keys = {category["key"] for category in categories}
    fallback_category = "free" if "free" in category_keys else next(iter(category_keys), "")
    for item in data.get("candidates", []):
        category_key = str(item.get("category_key") or fallback_category)
        if category_key not in category_keys:
            category_key = fallback_category
        candidate = ProposedConceptUpdate(
            project_id=document.project_id,
            document_id=document.id,
            title=str(item.get("title") or "새 설정 후보"),
            category_key=category_key,
            candidate_sentence=str(item.get("candidate_sentence") or ""),
            summary=str(item.get("summary") or ""),
            body=str(item.get("candidate_sentence") or ""),
            source_excerpt=str(item.get("source_excerpt") or ""),
            evidence_json={"related_page_ids": item.get("related_page_ids", [])},
            conflict_json={"risk": item.get("conflict_risk", "unknown")},
            status="CANDIDATE",
        )
        db.add(candidate)
        created.append(candidate)
    db.add(
        GenerationRun(
            project_id=document.project_id,
            session_id=document.session_id,
            document_id=document.id,
            task="extract_candidates",
            model_role="utility",
            model=result.model,
            endpoint=result.endpoint,
            params_json=result.params,
            usage_json=result.usage,
            input_json={
                "document_id": document.id,
                "known_page_ids": [item["id"] for item in known_pages],
            },
            output_text=result.content,
        )
    )
    db.commit()
    for candidate in created:
        db.refresh(candidate)
    return created


@router.post("/reference-analyzer/{page_id}", response_model=ReferenceAnalysisRead)
async def run_reference_analyzer(page_id: str, db: Session = Depends(get_db)) -> ReferenceAnalysis:
    page = _get_or_404(db, ConceptPage, page_id, "참고 페이지")
    if page.usage_role != "DISCOURSE_REFERENCE":
        raise _error(
            409,
            "REFERENCE_ROLE_REQUIRED",
            "Reference Analyzer는 DISCOURSE_REFERENCE 페이지에만 실행할 수 있습니다.",
        )
    body = tiptap_to_text(page.body_json)
    try:
        data, result = await analyze_reference(harness.gateway, body)
    except ModelGatewayError as exc:
        raise _error(502, exc.code, str(exc)) from exc
    analysis = ReferenceAnalysis(
        project_id=page.project_id,
        concept_page_id=page.id,
        analysis_json={"paragraphs": data.get("paragraphs", [])},
        recipe_candidate_json=data.get("recipe_candidate", {}),
        voice_candidate_json=data.get("voice_candidate", {}),
        similarity_report_json={"risks": data.get("similarity_risks", [])},
        status="CANDIDATE",
    )
    db.add(analysis)
    db.add(
        GenerationRun(
            project_id=page.project_id,
            task="reference_analysis",
            model_role="utility",
            model=result.model,
            endpoint=result.endpoint,
            params_json=result.params,
            usage_json=result.usage,
            input_json={"concept_page_id": page.id},
            output_text=result.content,
        )
    )
    db.commit()
    db.refresh(analysis)
    return analysis


@router.post("/reference-analyses/{analysis_id}/approve")
def approve_reference_analysis(
    analysis_id: str,
    payload: ReferenceAnalysisApprovalRequest | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    analysis = _get_or_404(db, ReferenceAnalysis, analysis_id, "참고 분석")
    if analysis.status != "CANDIDATE":
        raise _error(409, "ANALYSIS_ALREADY_DECIDED", "이미 처리된 참고 분석입니다.")
    payload = payload or ReferenceAnalysisApprovalRequest()
    page = _get_or_404(db, ConceptPage, analysis.concept_page_id, "참고 페이지")
    recipe: WritingRecipe | None = None
    voice: VoiceProfile | None = None
    created_examples: list[VoiceProfileExample] = []
    if payload.approve_recipe:
        recipe_key = f"reference_{analysis.id[:8]}"
        recipe_name = f"참고 분석 {analysis.id[:8]}"
        recipe_description = "사용자가 승인한 DISCOURSE_REFERENCE 구조 분석"
        recipe = WritingRecipe(
            project_id=analysis.project_id,
            key=recipe_key,
            version="1.0.0",
            name=recipe_name,
            description=recipe_description,
            recipe_json=_recipe_json_with_identity(
                _normalize_reference_recipe(analysis),
                key=recipe_key,
                version="1.0.0",
                name=recipe_name,
                description=recipe_description,
            ),
            approved=True,
        )
        db.add(recipe)

    if payload.approve_voice_profile:
        candidate = canonicalize_voice_profile_json(
            {
                key: value
                for key, value in dict(analysis.voice_candidate_json or {}).items()
                if key in VOICE_PROFILE_FIELDS
            }
        )
        selected_fields = payload.selected_voice_fields or [
            field for field, value in candidate.items() if value and field != "compatibility"
        ]
        selected_profile = {
            field: value
            for field, value in candidate.items()
            if field in selected_fields or field == "compatibility"
        }
        selected_profile = canonicalize_voice_profile_json(selected_profile)
        if not selected_profile.get("reader_effect"):
            selected_profile["reader_effect"] = "참고 글에서 승인한 절제와 리듬을 유지한다."
        profile_project_id = analysis.project_id if payload.voice_scope == "PROJECT" else None
        voice = VoiceProfile(
            project_id=profile_project_id,
            key=f"reference_{analysis.id[:8]}",
            version="1.0.0",
            name=f"참고 문체 {analysis.id[:8]}",
            description=selected_profile["reader_effect"],
            profile_json=selected_profile,
            source_analysis_id=analysis.id if profile_project_id else None,
            is_builtin=False,
            status="APPROVED",
        )
        db.add(voice)
        db.flush()
        body = tiptap_to_text(page.body_json)
        for index, selected_range in enumerate(payload.selected_example_ranges):
            excerpt = body[selected_range.start : selected_range.end].strip()
            if not excerpt:
                continue
            example = VoiceProfileExample(
                voice_profile_id=voice.id,
                source_concept_page_id=page.id if profile_project_id else None,
                label=selected_range.label,
                excerpt=excerpt,
                teaches_json=selected_range.teaches_json,
                scene_tags=selected_range.scene_tags,
                rights_basis=payload.rights_basis,
                use_in_generation=payload.rights_basis != "ANALYSIS_ONLY",
                position=index,
                status="ACTIVE",
                excerpt_hash=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            )
            db.add(example)
            created_examples.append(example)

    analysis.status = "APPROVED"
    page.properties_json = {
        **(page.properties_json or {}),
        "approved_analysis": {
            "analysis_id": analysis.id,
            "paragraphs": analysis.analysis_json.get("paragraphs", []),
            "recipe_id": recipe.id if recipe else None,
            "voice_profile_id": voice.id if voice else None,
            "fact_eligible": False,
        },
    }
    db.add_all([analysis, page])
    db.add(
        AuditLog(
            project_id=analysis.project_id,
            action="APPROVE_REFERENCE_ANALYSIS",
            entity_type="ReferenceAnalysis",
            entity_id=analysis.id,
            before_json={"status": "CANDIDATE"},
            after_json={
                "status": "APPROVED",
                "recipe_id": recipe.id if recipe else None,
                "voice_profile_id": voice.id if voice else None,
                "selected_voice_fields": payload.selected_voice_fields,
                "example_count": len(created_examples),
            },
            reason="사용자 명시 승인",
        )
    )
    db.commit()
    return {
        "analysis_id": analysis.id,
        "status": analysis.status,
        "recipe_id": recipe.id if recipe else None,
        "voice_profile_id": voice.id if voice else None,
        "example_ids": [example.id for example in created_examples],
    }


@router.get("/candidates", response_model=list[CandidateRead])
def list_candidates(
    project_id: str = Query(...), db: Session = Depends(get_db)
) -> list[ProposedConceptUpdate]:
    return list(
        db.scalars(
            select(ProposedConceptUpdate)
            .where(ProposedConceptUpdate.project_id == project_id)
            .order_by(ProposedConceptUpdate.created_at.desc())
        ).all()
    )


@router.post("/candidates/{candidate_id}/decide", response_model=CandidateRead)
def decide_candidate(
    candidate_id: str, payload: CandidateDecision, db: Session = Depends(get_db)
) -> ProposedConceptUpdate:
    candidate = _get_or_404(db, ProposedConceptUpdate, candidate_id, "설정 후보")
    if candidate.status != "CANDIDATE":
        raise _error(409, "CANDIDATE_ALREADY_DECIDED", "이미 처리된 설정 후보입니다.")
    decision = payload.decision
    if decision in {"discard", "reject"}:
        candidate.status = "REJECTED"
    elif decision == "this_document_only":
        candidate.status = "THIS_DOCUMENT_ONLY"
    elif decision in {"save_draft", "approve_canon"}:
        category_key = _resolve_category_key(db, candidate.project_id, candidate.category_key)
        page = ConceptPage(
            project_id=candidate.project_id,
            title=candidate.title,
            category_key=category_key,
            usage_role="CANDIDATE",
            authority_state="CANDIDATE",
            namespace=_get_or_404(db, Project, candidate.project_id, "프로젝트").universe_namespace,
            summary=candidate.summary,
            body_json={
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": candidate.body}],
                    }
                ],
            },
        )
        db.add(page)
        db.flush()
        add_concept_revision(db, page, reason="candidate_created")
        db.commit()
        promote_page(db, page, target_state="DRAFT_SETTING", reason=payload.reason)
        if decision == "approve_canon":
            promote_page(db, page, target_state="PROJECT_CANON", reason=payload.reason)
        candidate.approved_page_id = page.id
        candidate.status = "ACCEPTED_AS_CANON" if decision == "approve_canon" else "ACCEPTED_AS_DRAFT"
    else:
        raise _error(
            422,
            "INVALID_CANDIDATE_DECISION",
            "discard, this_document_only, save_draft, approve_canon 중 하나를 선택하십시오.",
        )
    db.add(candidate)
    db.add(
        AuditLog(
            project_id=candidate.project_id,
            action="DECIDE_CANDIDATE",
            entity_type="ProposedConceptUpdate",
            entity_id=candidate.id,
            before_json={"status": "CANDIDATE"},
            after_json={
                "status": candidate.status,
                "approved_page_id": candidate.approved_page_id,
            },
            reason=payload.reason,
        )
    )
    db.commit()
    db.refresh(candidate)
    return candidate


@router.post("/index/jobs", response_model=IndexJobRead, status_code=status.HTTP_201_CREATED)
def create_index_job(payload: ReindexRequest, db: Session = Depends(get_db)) -> IndexJob:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    if payload.concept_page_id:
        page = _get_or_404(db, ConceptPage, payload.concept_page_id, "컨셉 페이지")
        _require_project(page, payload.project_id, "컨셉 페이지")
    job = IndexJob(**payload.model_dump(), action="REINDEX", status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/index/jobs/{job_id}/run", response_model=IndexJobRead)
async def execute_index_job(job_id: str, db: Session = Depends(get_db)) -> IndexJob:
    job = _get_or_404(db, IndexJob, job_id, "인덱스 작업")
    result = await run_index_job(db, job, harness.gateway)
    if result.status == "FAILED":
        raise _error(
            502,
            result.error_json.get("code", "INDEXING_FAILED"),
            result.error_json.get("message", "재색인 실패"),
        )
    return result


@router.post("/search")
async def search_concepts(payload: SearchRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    return await hybrid_search(db, **payload.model_dump(), gateway=harness.gateway)


@router.get("/index/stats")
def get_index_stats(project_id: str = Query(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    _get_or_404(db, Project, project_id, "프로젝트")
    return index_stats(db, project_id)
