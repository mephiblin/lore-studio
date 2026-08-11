import asyncio
import json

import httpx
from conftest import HandlerTransport, isolated_session
from sqlalchemy import select

from app.config import settings
from app.models import (
    AuditFinding,
    GenerationRun,
    GenerationStage,
    LoreBlock,
    PlaybookSession,
    Project,
    WritingRecipe,
)
from app.services.harness import LoreHarness, _long_form_foci, _near_duplicate_count
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
            user_payload = json.loads(payload["messages"][-1]["content"])
            if "revision_brief" in user_payload:
                content = ("초안의 사실을 유지하며 문단 사이의 연결과 의미를 보강한다. " * 28).strip()
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
    plan = asyncio.run(harness.plan(db, session))
    assert [block["move"] for block in plan["blocks"]] == ["ORIENT", "ANCHOR", "WITHHOLD"]
    assert "필수 순서" in " ".join(plan["warnings"])
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
    draft_run = db.scalar(select(GenerationRun).where(GenerationRun.task == "draft"))
    assert draft_run is not None
    assert draft_run.prompt_components["sampling_profile"] == "balanced"
    assert draft_run.params_json["sampling_profile_snapshot"]["parameters"]["top_k"] == 32
    recipe_warning = db.scalar(
        select(AuditFinding).where(
            AuditFinding.document_id == document.id,
            AuditFinding.code == "RECIPE_SEQUENCE_MISMATCH",
        )
    )
    assert recipe_warning is not None
    assert recipe_warning.evidence_json["required_moves"] == ["ORIENT", "ANCHOR", "WITHHOLD"]

    result = asyncio.run(
        harness.finalize_document(
            db,
            document,
            instruction="문단 사이의 시간 흐름을 연결한다.",
            refinement_json={
                "priorities": ["coherence", "imagery", "ending"],
                "intensity": "strong",
                "length_policy": "expand",
            },
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
    assert final_run.input_json["revision_brief"]["priorities"] == [
        "coherence",
        "imagery",
        "ending",
    ]
    assert final_run.input_json["revision_brief"]["intensity"] == "strong"
    assert final_run.input_json["revision_brief"]["length_policy"] == "expand"
    reused = final_run.input_json["original_writing_request"]
    assert reused["refinement"]["priority_instructions"]
    assert reused["user_direction"] == "도시의 대가를 마지막까지 숨기지 않는다."
    assert reused["output_profile"]["key"] == "lore_article"
    assert reused["generation_settings"]["viewpoint"] == "third_limited"
    assert reused["generation_settings"]["tense"] == "past"
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


def test_long_form_completion_fills_measured_character_target(monkeypatch) -> None:
    monkeypatch.setattr(settings, "writer_model_base_url", "http://models.test/v1")
    monkeypatch.setattr(settings, "writer_model_name", "writer-test")
    monkeypatch.setattr(settings, "model_retry_attempts", 0)

    async def model_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "writer-test"}]})
        payload = json.loads(request.content)
        user_payload = json.loads(payload["messages"][-1]["content"])
        contract = user_payload["long_form_contract"]
        requested = contract["requested_new_characters"]
        marker = chr(0xAC00 + contract["block_number"] * 100)
        sentence = marker * 96 + ". "
        content = (sentence * (requested // len(sentence) + 1))[:requested].rstrip()
        if not content.endswith("."):
            content += "."
        return httpx.Response(
            200,
            json={
                "model": payload["model"],
                "choices": [{"message": {"content": content}}],
                "usage": {"completion_tokens": requested},
            },
        )

    harness = LoreHarness(ModelGateway(transport=HandlerTransport(model_handler)))
    result, paragraph_indexes = asyncio.run(
        harness._complete_long_form(
            system_prompt="테스트 장문 작성자",
            source_payload={"context_pack": {"locked_facts": ["사실"]}},
            plan={
                "blocks": [
                    {"move": "ORIENT", "purpose": "도입", "word_budget": 3000},
                    {"move": "SYNTHESIZE", "purpose": "수렴", "word_budget": 3000},
                ]
            },
            target=6000,
            temperature=0.5,
            seed=7,
            mode="draft",
        )
    )

    assert len(result.content) >= 5700
    assert result.params["strategy"] == "block_segments"
    assert result.params["target_characters"] == 6000
    assert result.params["actual_characters"] == len(result.content)
    assert result.params["call_count"] >= 2
    assert len(paragraph_indexes) == 2


def test_long_form_duplicate_audit_catches_rephrased_paragraphs() -> None:
    first = (
        "대상은 돌무덤 2층에 고정되어 있으며 차가운 환경 속에서 미라 형태를 유지한다. "
        "이 관찰은 물리적 보존과 공간적 고립의 관계를 보여 준다."
    )
    rephrased = (
        "대상은 돌무덤 2층에 고정되어 있고 차가운 환경에서 미라의 형태를 유지한다. "
        "이 관찰은 공간적 고립과 물리적 보존의 관계를 보여 준다."
    )

    assert _near_duplicate_count(f"{first}\n\n{rephrased}") == 1
    assert "인물" in _long_form_foci(
        {"context_pack": {"output_profile": {"key": "novel_prose"}}}
    )[0]
    assert "경험" in _long_form_foci(
        {"original_writing_request": {"output_profile": {"key": "personal_essay"}}}
    )[0]
