import asyncio
import json

import httpx
from conftest import HandlerTransport, isolated_session
from sqlalchemy import select

from app.config import settings
from app.models import GenerationRun, GenerationStage, LoreBlock, PlaybookSession, Project, WritingRecipe
from app.services.harness import LoreHarness
from app.services.model_gateway import ModelGateway


def test_generation_persists_required_stages_and_lore_blocks(monkeypatch) -> None:
    monkeypatch.setattr(settings, "utility_model_base_url", "http://models.test/v1")
    monkeypatch.setattr(settings, "utility_model_name", "utility-test")
    monkeypatch.setattr(settings, "writer_model_base_url", "http://models.test/v1")
    monkeypatch.setattr(settings, "writer_model_name", "writer-test")
    monkeypatch.setattr(settings, "model_retry_attempts", 0)

    async def model_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "utility-test"}, {"id": "writer-test"}]})
        payload = json.loads(request.content)
        if payload["model"] == "utility-test":
            content = json.dumps(
                {
                    "title": "파이프라인 검증",
                    "angle": "저장 경계를 검증한다.",
                    "blocks": [
                        {
                            "move": "ORIENT",
                            "purpose": "맥락을 설명한다.",
                            "evidence_ids": [],
                            "word_budget": 300,
                            "must_include": [],
                            "avoid": [],
                        }
                    ],
                    "warnings": [],
                },
                ensure_ascii=False,
            )
        else:
            content = "첫 문단은 선택한 설정의 맥락을 설명한다.\n\n둘째 문단은 근거와 결론을 연결한다."
        return httpx.Response(
            200,
            json={"model": payload["model"], "choices": [{"message": {"content": content}}], "usage": {}},
        )

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
        user_direction="도시의 대가를 마지막까지 숨기지 않는다.",
        output_profile="lore_article",
        settings_json={
            "length": "short",
            "context_depth": "core",
            "viewpoint": "third_limited",
            "tense": "past",
        },
        seed=7,
    )
    db.add(session)
    db.commit()

    harness = LoreHarness(ModelGateway(transport=HandlerTransport(model_handler)))
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

    result = asyncio.run(
        harness.finalize_document(
            db,
            document,
            instruction="문단 사이의 시간 흐름을 연결한다.",
            user_direction="완성본에서는 시민의 시선을 중심에 둔다.",
            output_profile="novel_prose",
            settings_json={"viewpoint": "first_observer", "tense": "present"},
        )
    )
    assert result["status"] == "ready"
    assert result["draft_changed"] is False
    lorebook_entry = result["lorebook_entry"]
    assert lorebook_entry is not None
    assert lorebook_entry.document_kind == "lorebook"
    assert lorebook_entry.source_document_id == document.id
    assert lorebook_entry.body_markdown
    assert lorebook_entry.source_draft_hash == result["current_draft_hash"]
    assert document.document_kind == "draft"
    assert document.body_markdown

    final_run = db.scalar(
        select(GenerationRun).where(
            GenerationRun.session_id == session.id,
            GenerationRun.task == "finalize",
        )
    )
    assert final_run is not None
    assert final_run.input_json["editable_draft"]
    reused = final_run.input_json["original_writing_request"]
    assert reused["user_direction"] == "완성본에서는 시민의 시선을 중심에 둔다."
    assert reused["output_profile"]["key"] == "novel_prose"
    assert reused["generation_settings"]["viewpoint"] == "first_observer"
    assert reused["generation_settings"]["tense"] == "present"
    assert session.user_direction == "도시의 대가를 마지막까지 숨기지 않는다."
    assert db.scalar(
        select(GenerationStage).where(GenerationStage.step == "FINAL_COHERENCE_PASS")
    ) is not None

    first_block = db.scalar(
        select(LoreBlock)
        .where(LoreBlock.document_id == document.id)
        .order_by(LoreBlock.position)
    )
    assert first_block is not None
    first_block.content_markdown += " 수정됨."
    db.commit()
    assert harness.finalization_summary(db, document)["status"] == "stale"
