from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import ConceptPage, DirectionCard, LoreDocument, PlaybookSession, Project, WritingRecipe
from app.schemas import (
    ConceptPageCreate,
    ConceptPageRead,
    ConceptPageUpdate,
    DirectionCardCreate,
    DirectionCardRead,
    GenerationResult,
    LoreDocumentRead,
    LoreDocumentUpdate,
    PlaybookSessionCreate,
    PlaybookSessionRead,
    ProjectCreate,
    ProjectRead,
    WritingRecipeRead,
)
from app.services.config_loader import load_direction_card_presets, load_output_profiles, load_page_templates
from app.services.harness import LoreHarness


router = APIRouter()
harness = LoreHarness()


def _get_or_404(db: Session, model: type[Any], object_id: str, label: str) -> Any:
    obj = db.get(model, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{label}을(를) 찾을 수 없습니다.")
    return obj


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/models/status")
async def model_status() -> dict[str, Any]:
    """Return model availability without exposing endpoints or credentials."""
    return {"mock_mode": settings.mock_model, "profiles": await harness.gateway.health_all()}


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


@router.post("/concept-pages", response_model=ConceptPageRead, status_code=status.HTTP_201_CREATED)
def create_concept_page(payload: ConceptPageCreate, db: Session = Depends(get_db)) -> ConceptPage:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    page = ConceptPage(**payload.model_dump())
    db.add(page)
    db.commit()
    db.refresh(page)
    return page


@router.get("/concept-pages", response_model=list[ConceptPageRead])
def list_concept_pages(
    project_id: str = Query(...),
    usage_role: str | None = None,
    category_key: str | None = None,
    db: Session = Depends(get_db),
) -> list[ConceptPage]:
    stmt = select(ConceptPage).where(ConceptPage.project_id == project_id)
    if usage_role:
        stmt = stmt.where(ConceptPage.usage_role == usage_role)
    if category_key:
        stmt = stmt.where(ConceptPage.category_key == category_key)
    stmt = stmt.order_by(ConceptPage.updated_at.desc())
    return list(db.scalars(stmt).all())


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
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(page, key, value)
    db.add(page)
    db.commit()
    db.refresh(page)
    return page


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


@router.get("/writing-recipes", response_model=list[WritingRecipeRead])
def list_writing_recipes(db: Session = Depends(get_db)) -> list[WritingRecipe]:
    return list(db.scalars(select(WritingRecipe).order_by(WritingRecipe.name)).all())


@router.post("/playbook-sessions", response_model=PlaybookSessionRead, status_code=status.HTTP_201_CREATED)
def create_playbook_session(payload: PlaybookSessionCreate, db: Session = Depends(get_db)) -> PlaybookSession:
    _get_or_404(db, Project, payload.project_id, "프로젝트")
    _get_or_404(db, WritingRecipe, payload.writing_recipe_id, "집필 레시피")
    session = PlaybookSession(**payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/playbook-sessions/{session_id}", response_model=PlaybookSessionRead)
def get_playbook_session(session_id: str, db: Session = Depends(get_db)) -> PlaybookSession:
    return _get_or_404(db, PlaybookSession, session_id, "플레이북 세션")


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


@router.get("/documents", response_model=list[LoreDocumentRead])
def list_documents(project_id: str = Query(...), db: Session = Depends(get_db)) -> list[LoreDocument]:
    return list(
        db.scalars(
            select(LoreDocument)
            .where(LoreDocument.project_id == project_id)
            .order_by(LoreDocument.updated_at.desc())
        ).all()
    )


@router.get("/documents/{document_id}", response_model=LoreDocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)) -> LoreDocument:
    return _get_or_404(db, LoreDocument, document_id, "로어 문서")


@router.patch("/documents/{document_id}", response_model=LoreDocumentRead)
def update_document(
    document_id: str,
    payload: LoreDocumentUpdate,
    db: Session = Depends(get_db),
) -> LoreDocument:
    document = _get_or_404(db, LoreDocument, document_id, "로어 문서")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(document, key, value)
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
