import asyncio

from conftest import isolated_session
from sqlalchemy import select

from app.config import settings
from app.models import GenerationRun, GenerationStage, LoreBlock, PlaybookSession, Project, WritingRecipe
from app.services.harness import LoreHarness


def test_generation_persists_required_stages_and_lore_blocks(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mock_model", True)
    db = isolated_session()
    project = Project(name="파이프라인", slug="pipeline")
    recipe = WritingRecipe(
        key="test",
        version="1",
        name="테스트",
        recipe_json={
            "key": "test",
            "version": "1",
            "moves": [
                {"id": "ORIENT", "purpose": "맥락"},
                {"id": "ANCHOR", "purpose": "사실"},
                {"id": "WITHHOLD", "purpose": "미지"},
            ],
            "required_moves": ["ORIENT", "ANCHOR", "WITHHOLD"],
            "optional_moves": [],
        },
        is_builtin=True,
    )
    db.add_all([project, recipe])
    db.flush()
    session = PlaybookSession(
        project_id=project.id,
        writing_recipe_id=recipe.id,
        settings_json={"length": "short", "context_depth": "core"},
        seed=7,
    )
    db.add(session)
    db.commit()

    harness = LoreHarness()
    harness.context_preview(db, session)
    asyncio.run(harness.plan(db, session))
    document = asyncio.run(harness.generate(db, session))

    stages = set(db.scalars(select(GenerationStage.step)).all())
    assert {
        "COMPILE_CONTEXT",
        "SELECT_ANGLE",
        "PLAN",
        "USER_EDITABLE_PLAN",
        "DRAFT_BLOCKS",
        "COHERENCE_PASS",
        "CANON_AUDIT",
        "DISCOURSE_AUDIT",
        "STYLE_AUDIT",
        "SAVE_REVISION",
    }.issubset(stages)
    assert db.query(LoreBlock).filter_by(document_id=document.id).count() >= 1
    assert db.query(GenerationRun).filter_by(session_id=session.id).count() == 2
