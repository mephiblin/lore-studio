from __future__ import annotations

import difflib
import json
from typing import Any

import markdown
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
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
    WritingRecipe,
    new_id,
)
from app.schemas import (
    AuditFindingRead,
    AuthorityPromotion,
    CandidateCreate,
    CandidateDecision,
    CandidateRead,
    CategoryDefinitionCreate,
    CategoryDefinitionRead,
    CategoryDefinitionUpdate,
    ConceptPageCreate,
    ConceptPageRead,
    ConceptPageUpdate,
    ConceptRelationCreate,
    ConceptRelationRead,
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
    ReferenceAnalysisRead,
    ReindexRequest,
    RewriteRequest,
    SearchRequest,
    WritingRecipeCreate,
    WritingRecipeRead,
    WritingRecipeUpdate,
)
from app.services.authority import AUTHORITY_STATES, AuthorityTransitionError, promote_page
from app.services.config_loader import (
    load_direction_card_presets,
    load_output_profiles,
    load_page_templates,
    seed_project_categories,
)
from app.services.context_compiler import compile_context, tiptap_to_text
from app.services.harness import LoreHarness
from app.services.model_gateway import ModelGatewayError
from app.services.revisions import add_concept_revision, add_lore_revision
from app.services.search import hybrid_search, index_stats, run_index_job
from app.services.utility_tools import analyze_image, analyze_reference, extract_candidates, suggest_direction

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


RECIPE_MOVE_LABELS = {
    "ORIENT": "배경 설명",
    "NARROW": "주제로 초점 이동",
    "ANCHOR": "핵심 사실 제시",
    "COMPLICATE": "문제·예외 추가",
    "COMPARE": "차이 비교",
    "EXEMPLIFY": "사례 제시",
    "ESCALATE": "긴장 고조",
    "INTERPRET": "의미 해설",
    "WITHHOLD": "의문 남기기",
    "TURN": "관점 전환",
    "STING": "마지막 여운",
}


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
    allowed = set(RECIPE_MOVE_LABELS)
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

    preview = [str(item).strip() for item in candidate.get("pattern_preview", []) if str(item).strip()]
    if len(preview) != len(required):
        preview = [RECIPE_MOVE_LABELS[move] for move in required]

    defined_moves = {
        str(item.get("id", "")).strip().upper(): str(item.get("purpose", "")).strip()
        for item in candidate.get("moves", [])
        if isinstance(item, dict) and str(item.get("id", "")).strip().upper() in allowed
    }
    moves = [
        {"id": move, "purpose": defined_moves.get(move) or RECIPE_MOVE_LABELS[move]}
        for move in dict.fromkeys(required)
    ]
    return {
        **candidate,
        "pattern_preview": preview,
        "required_moves": required,
        "optional_moves": [
            str(move).strip().upper()
            for move in candidate.get("optional_moves", [])
            if str(move).strip().upper() in allowed and str(move).strip().upper() not in required
        ],
        "moves": moves,
        "planner_rules": [str(rule) for rule in candidate.get("planner_rules", [])],
        "audit_rules": [str(rule) for rule in candidate.get("audit_rules", [])],
    }


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
        raise _error(404, "PROJECT_SCOPE_MISMATCH", f"이 프로젝트에서 {label}을(를) 찾을 수 없습니다.")


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
    db.delete(project)
    db.commit()


@router.post("/categories", response_model=CategoryDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryDefinitionCreate, db: Session = Depends(get_db)
) -> CategoryDefinition:
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
def list_categories(
    project_id: str = Query(...), db: Session = Depends(get_db)
) -> list[CategoryDefinition]:
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
    page_count = db.scalar(
        select(func.count(ConceptPage.id)).where(
            ConceptPage.project_id == category.project_id,
            ConceptPage.category_key == category.key,
        )
    ) or 0
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


@router.post("/concept-pages", response_model=ConceptPageRead, status_code=status.HTTP_201_CREATED)
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
            (ConceptRelation.source_page_id == related_to)
            | (ConceptRelation.target_page_id == related_to),
        )
        if relation_type:
            relation_stmt = relation_stmt.where(ConceptRelation.relation_type == relation_type)
        related_ids: set[str] = set()
        for relation in db.scalars(relation_stmt):
            related_ids.add(
                relation.target_page_id
                if relation.source_page_id == related_to
                else relation.source_page_id
            )
        stmt = stmt.where(ConceptPage.id.in_(related_ids or {"__no_related_page__"}))
    stmt = stmt.order_by(ConceptPage.updated_at.desc())
    pages = list(db.scalars(stmt).all())
    if tag:
        pages = [page for page in pages if tag in (page.tags or [])]
    return pages


@router.get("/concept-pages/{page_id}", response_model=ConceptPageRead)
def get_concept_page(page_id: str, db: Session = Depends(get_db)) -> ConceptPage:
    return _get_or_404(db, ConceptPage, page_id, "컨셉 페이지")


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


@router.post("/concept-relations", response_model=ConceptRelationRead, status_code=status.HTTP_201_CREATED)
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
            .where(
                (ConceptRelation.source_page_id == page_id)
                | (ConceptRelation.target_page_id == page_id)
            )
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
        raise _error(422, "IMAGE_DATA_URL_REQUIRED", "브라우저에서 읽은 image data URL이 필요합니다.")
    try:
        suggestion, result = await analyze_image(
            harness.gateway, payload.image_data_url, payload.instruction
        )
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


@router.post("/direction-cards", response_model=DirectionCardRead, status_code=status.HTTP_201_CREATED)
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
def list_writing_recipes(
    project_id: str | None = None, db: Session = Depends(get_db)
) -> list[WritingRecipe]:
    stmt = select(WritingRecipe).where(WritingRecipe.approved.is_(True))
    if project_id:
        stmt = stmt.where(
            (WritingRecipe.project_id == project_id) | (WritingRecipe.project_id.is_(None))
        )
    else:
        # The playbook's progression choices are global presets. Project recipes
        # created by reference analysis must never leak into another project.
        stmt = stmt.where(WritingRecipe.project_id.is_(None))
    rows = list(db.scalars(stmt.order_by(WritingRecipe.updated_at.desc())).all())
    latest: dict[tuple[str | None, str], WritingRecipe] = {}
    for recipe in rows:
        latest.setdefault((recipe.project_id, recipe.key), recipe)
    return sorted(latest.values(), key=lambda recipe: (recipe.name, recipe.version), reverse=False)


@router.post("/writing-recipes", response_model=WritingRecipeRead, status_code=status.HTTP_201_CREATED)
def create_writing_recipe(
    payload: WritingRecipeCreate, db: Session = Depends(get_db)
) -> WritingRecipe:
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
    in_use = db.scalar(
        select(PlaybookSession.id).where(PlaybookSession.writing_recipe_id == recipe.id)
    )
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


@router.post("/playbook-sessions", response_model=PlaybookSessionRead, status_code=status.HTTP_201_CREATED)
def create_playbook_session(payload: PlaybookSessionCreate, db: Session = Depends(get_db)) -> PlaybookSession:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    recipe = _get_or_404(db, WritingRecipe, payload.writing_recipe_id, "전개 방식")
    _require_recipe_for_project(recipe, payload.project_id)
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
async def stream_generate_session(
    session_id: str, db: Session = Depends(get_db)
) -> StreamingResponse:
    session = _get_or_404(db, PlaybookSession, session_id, "플레이북 세션")

    async def events():  # type: ignore[no-untyped-def]
        yield "event: progress\ndata: " + json.dumps(
            {"step": "DRAFT_BLOCKS", "message": "Writer가 LoreBlock 원고를 작성하고 있습니다."},
            ensure_ascii=False,
        ) + "\n\n"
        try:
            document = await harness.generate(db, session)
            db.refresh(session)
            payload = GenerationResult(session=session, document=document, plan=session.plan_json)
            yield "event: complete\ndata: " + json.dumps(
                jsonable_encoder(payload), ensure_ascii=False
            ) + "\n\n"
        except (ModelGatewayError, ValueError) as exc:
            yield "event: error\ndata: " + json.dumps(
                {"code": getattr(exc, "code", "GENERATION_FAILED"), "message": str(exc)},
                ensure_ascii=False,
            ) + "\n\n"

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
            select(LoreBlock)
            .where(LoreBlock.document_id == document_id)
            .order_by(LoreBlock.position)
        ).all()
    )
    by_id = {block.id: block for block in existing}
    incoming_ids = [item.id for item in payload.blocks if item.id]
    if len(incoming_ids) != len(set(incoming_ids)):
        raise _error(422, "DUPLICATE_BLOCK", "같은 문단이 두 번 포함되어 있습니다.")
    unknown_ids = [block_id for block_id in incoming_ids if block_id not in by_id]
    if unknown_ids:
        raise _error(422, "BLOCK_SCOPE_MISMATCH", "이 초안에 속하지 않은 문단이 포함되어 있습니다.")

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
            select(LoreBlock)
            .where(LoreBlock.document_id == document_id)
            .order_by(LoreBlock.position)
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
            select(LoreBlock)
            .where(LoreBlock.document_id == document.id)
            .order_by(LoreBlock.position)
        ).all()
    )
    _sync_draft_document(document, blocks)
    db.add_all([block, document])
    add_lore_revision(db, document, reason="user_block_save", author_type="user")
    db.commit()
    db.refresh(block)
    return block


@router.get("/documents/{document_id}/finalization", response_model=FinalizationRead)
def get_document_finalization(
    document_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
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
    try:
        return await harness.finalize_document(
            db,
            document,
            instruction=payload.instruction,
            user_direction=payload.user_direction,
            writing_recipe_id=payload.writing_recipe_id,
            output_profile=payload.output_profile,
            settings_json=payload.settings_json,
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
    prompt = (
        "다음 한국어 문단을 재작성하라. 새 고유 사실을 만들지 말고 결과 문단만 출력하라.\n"
        f"작업: {instruction}\n추가 지시: {payload.instruction}\n원문:\n{block.content_markdown}"
    )
    try:
        result = await harness.gateway.complete(
            [{"role": "user", "content": prompt}],
            role="writer",
            temperature=0.45,
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
        input_hash="",
        input_json={"block_id": block.id, "operation": payload.operation, "original": block.content_markdown},
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
            select(LoreBlock)
            .where(LoreBlock.document_id == document.id)
            .order_by(LoreBlock.position)
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
            select(LoreBlock)
            .where(LoreBlock.document_id == document.id)
            .order_by(LoreBlock.position)
        ).all()
    )
    draft_body = "\n\n".join(item.content_markdown for item in blocks) or document.body_markdown
    if format == "markdown":
        value = draft_body
        if include_metadata:
            value += "\n\n<!-- lore-studio: " + json.dumps(
                [{"id": item.id, "move": item.rhetorical_move, "evidence": item.evidence_ids} for item in blocks],
                ensure_ascii=False,
            ) + " -->"
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
            select(LoreBlock)
            .where(LoreBlock.document_id == document.id)
            .order_by(LoreBlock.position)
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
            {"id": item["id"], "title": item["title"], "summary": item.get("summary", "")}
            for item in pack.get("selected_concepts", [])
        ]
    else:
        pages = db.scalars(
            select(ConceptPage).where(ConceptPage.project_id == document.project_id)
        ).all()
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
            input_json={"document_id": document.id, "known_page_ids": [item["id"] for item in known_pages]},
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
def approve_reference_analysis(analysis_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    analysis = _get_or_404(db, ReferenceAnalysis, analysis_id, "참고 분석")
    if analysis.status != "CANDIDATE":
        raise _error(409, "ANALYSIS_ALREADY_DECIDED", "이미 처리된 참고 분석입니다.")
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
    voice = VoiceProfile(
        project_id=analysis.project_id,
        name=f"참고 Voice {analysis.id[:8]}",
        profile_json=analysis.voice_candidate_json,
        source_analysis_id=analysis.id,
        approved=True,
    )
    analysis.status = "APPROVED"
    db.add_all([analysis, recipe, voice])
    db.add(
        AuditLog(
            project_id=analysis.project_id,
            action="APPROVE_REFERENCE_ANALYSIS",
            entity_type="ReferenceAnalysis",
            entity_id=analysis.id,
            before_json={"status": "CANDIDATE"},
            after_json={"status": "APPROVED"},
            reason="사용자 명시 승인",
        )
    )
    db.commit()
    return {"analysis_id": analysis.id, "status": analysis.status, "recipe_id": recipe.id, "voice_profile_id": voice.id}


@router.get("/candidates", response_model=list[CandidateRead])
def list_candidates(project_id: str = Query(...), db: Session = Depends(get_db)) -> list[ProposedConceptUpdate]:
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
        category_key = _resolve_category_key(
            db, candidate.project_id, candidate.category_key
        )
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
                    {"type": "paragraph", "content": [{"type": "text", "text": candidate.body}]}
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
            after_json={"status": candidate.status, "approved_page_id": candidate.approved_page_id},
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
        raise _error(502, result.error_json.get("code", "INDEXING_FAILED"), result.error_json.get("message", "재색인 실패"))
    return result


@router.post("/search")
async def search_concepts(payload: SearchRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    return await hybrid_search(db, **payload.model_dump(), gateway=harness.gateway)


@router.get("/index/stats")
def get_index_stats(project_id: str = Query(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    _get_or_404(db, Project, project_id, "프로젝트")
    return index_stats(db, project_id)
