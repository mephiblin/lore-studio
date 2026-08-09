from __future__ import annotations

import json
from pathlib import Path

from conftest import isolated_session
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import (
    ConceptPage,
    LoreBlock,
    LoreDocument,
    PlaybookSession,
    Project,
    ReferenceAnalysis,
    VoiceProfile,
    VoiceProfileExample,
    WritingRecipe,
)
from app.services.audits import prose_document_hash, run_prose_audits
from app.services.context_compiler import compile_context

VOICE_FIXTURES = Path(__file__).parent / "fixtures" / "voice_profiles.json"


def voice_rules() -> dict:
    return {
        "reader_effect": "절제된 문장 사이로 불안이 커진다.",
        "sentence_rhythm": ["짧은 행동문과 긴 관찰문을 교차한다."],
        "description_rules": ["감정을 행동과 감각으로 드러낸다."],
        "dialogue_rules": ["대사와 행동의 어긋남으로 서브텍스트를 만든다."],
        "figurative_language": ["장면 안의 사물에서 비유를 가져온다."],
        "paragraph_rules": ["관련 행동과 관찰을 한 문단에 축적한다."],
        "avoid_patterns": ["그는 매우 슬펐다"],
        "best_for": ["대치", "조사"],
        "audit_rules": ["인물별 대사 어휘가 구분되는가"],
        "compatibility": {"viewpoints": ["third_limited"], "tenses": ["past"]},
    }


def test_voice_fixture_contract_is_canonical_and_keeps_contamination_out() -> None:
    fixture = json.loads(VOICE_FIXTURES.read_text(encoding="utf-8"))
    assert len(fixture["profiles"]) == 3
    for profile in fixture["profiles"]:
        assert profile["profile_json"]["reader_effect"]
        assert set(profile["profile_json"]) == {
            "reader_effect",
            "sentence_rhythm",
            "description_rules",
            "dialogue_rules",
            "figurative_language",
            "paragraph_rules",
            "avoid_patterns",
            "best_for",
            "audit_rules",
            "compatibility",
        }
    assert fixture["contaminated_example"]["rights_basis"] == "ANALYSIS_ONLY"
    assert fixture["contaminated_example"]["use_in_generation"] is False
    assert fixture["golden_contract"] == {
        "voice_selection_mode": "profile_default",
        "fact_eligible": False,
        "excluded_rights_basis": "ANALYSIS_ONLY",
    }


def test_voice_profile_crud_scope_version_and_context_compilation() -> None:
    db = isolated_session()

    def override_db():  # type: ignore[no-untyped-def]
        yield db

    project_a = Project(name="북부 기록", slug="north-voice")
    project_b = Project(name="남부 기록", slug="south-voice")
    recipe = WritingRecipe(
        key="voice-test-recipe",
        version="1.0.0",
        name="문체 테스트 전개",
        recipe_json={"required_moves": ["ORIENT", "ANCHOR", "INTERPRET"]},
        is_builtin=True,
        approved=True,
    )
    db.add_all([project_a, project_b, recipe])
    db.commit()
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        created = client.post(
            "/api/v1/voice-profiles",
            json={
                "project_id": project_a.id,
                "name": "절제된 불안",
                "description": "말하지 않은 것이 오래 남는다.",
                "profile_json": voice_rules(),
            },
        )
        assert created.status_code == 201
        profile = created.json()
        assert profile["status"] == "DRAFT"

        analysis_only = client.post(
            f"/api/v1/voice-profiles/{profile['id']}/examples",
            json={
                "label": "분석 전용",
                "excerpt": "이 문장은 분석에만 쓰인다.",
                "rights_basis": "ANALYSIS_ONLY",
                "use_in_generation": True,
            },
        )
        assert analysis_only.status_code == 201
        assert analysis_only.json()["use_in_generation"] is False

        usable = client.post(
            f"/api/v1/voice-profiles/{profile['id']}/examples",
            json={
                "label": "자기 예시",
                "excerpt": "문이 닫혔다. 그는 손을 떼지 않았다. 복도의 공기가 조금씩 식었다.",
                "teaches_json": ["행동 뒤에 감각을 남긴다."],
                "scene_tags": ["대치"],
                "rights_basis": "SELF_AUTHORED",
                "use_in_generation": True,
            },
        )
        assert usable.status_code == 201
        usable_example = usable.json()

        not_approved = client.post(
            "/api/v1/playbook-sessions",
            json={
                "project_id": project_a.id,
                "writing_recipe_id": recipe.id,
                "voice_profile_id": profile["id"],
            },
        )
        assert not_approved.status_code == 422

        approved = client.post(f"/api/v1/voice-profiles/{profile['id']}/approve")
        assert approved.status_code == 200
        assert approved.json()["status"] == "APPROVED"

        cross_scope = client.get(
            f"/api/v1/voice-profiles/{profile['id']}",
            params={"project_id": project_b.id},
        )
        assert cross_scope.status_code == 404
        listed_b = client.get(
            "/api/v1/voice-profiles",
            params={"project_id": project_b.id, "status": "APPROVED"},
        ).json()
        assert profile["id"] not in {item["id"] for item in listed_b}

        session_response = client.post(
            "/api/v1/playbook-sessions",
            json={
                "project_id": project_a.id,
                "writing_recipe_id": recipe.id,
                "voice_profile_id": profile["id"],
                "voice_selection_mode": "manual",
                "voice_example_ids": [usable_example["id"]],
                "settings_json": {"viewpoint": "third_limited", "tense": "past"},
            },
        )
        assert session_response.status_code == 201
        session = db.get(PlaybookSession, session_response.json()["id"])
        assert session is not None
        pack = compile_context(db, session)
        assert pack["voice_profile"]["id"] == profile["id"]
        assert pack["style_examples"][0]["id"] == usable_example["id"]
        assert pack["style_examples"][0]["fact_eligible"] is False
        assert pack["voice_selection_mode"] == "manual"
        assert pack["excluded_style_examples"] == [
            {"id": analysis_only.json()["id"], "reason": "analysis_only_or_disabled"}
        ]
        assert "이 문장은 분석에만" not in str(pack)

        next_version = client.patch(
            f"/api/v1/voice-profiles/{profile['id']}",
            json={"description": "더 조용하고 긴 불안"},
        )
        assert next_version.status_code == 200
        assert next_version.json()["id"] != profile["id"]
        assert next_version.json()["status"] == "DRAFT"
        assert next_version.json()["version"] != profile["version"]
        cloned_examples = client.get(
            f"/api/v1/voice-profiles/{next_version.json()['id']}/examples"
        ).json()
        assert len(cloned_examples) == 2

        blocked_delete = client.delete(f"/api/v1/voice-profiles/{profile['id']}")
        assert blocked_delete.status_code == 409
        assert blocked_delete.json()["detail"]["code"] == "PROFILE_IN_USE"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_reference_analysis_can_approve_voice_without_recipe() -> None:
    db = isolated_session()

    def override_db():  # type: ignore[no-untyped-def]
        yield db

    project = Project(name="참고 분석", slug="reference-voice")
    db.add(project)
    db.flush()
    page = ConceptPage(
        project_id=project.id,
        title="자기 문체 표본",
        category_key="free",
        usage_role="DISCOURSE_REFERENCE",
        authority_state="DRAFT_SETTING",
        body_json={
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "문이 닫혔다. 복도에는 젖은 신발 자국만 남았다."}],
                }
            ],
        },
    )
    db.add(page)
    db.flush()
    analysis = ReferenceAnalysis(
        project_id=project.id,
        concept_page_id=page.id,
        analysis_json={"paragraphs": []},
        recipe_candidate_json={},
        voice_candidate_json=voice_rules(),
        similarity_report_json={"risks": []},
        status="CANDIDATE",
    )
    db.add(analysis)
    db.commit()
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/v1/reference-analyses/{analysis.id}/approve",
            json={
                "approve_recipe": False,
                "approve_voice_profile": True,
                "voice_scope": "PROJECT",
                "selected_voice_fields": ["reader_effect", "sentence_rhythm", "description_rules"],
                "selected_example_ranges": [],
                "rights_basis": "ANALYSIS_ONLY",
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["recipe_id"] is None
        voice = db.get(VoiceProfile, result["voice_profile_id"])
        assert voice is not None
        assert voice.status == "APPROVED"
        assert voice.project_id == project.id
        db.refresh(page)
        assert page.properties_json["approved_analysis"]["voice_profile_id"] == voice.id
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_prose_audit_detects_profile_conflict_and_reference_overlap() -> None:
    db = isolated_session()
    project = Project(name="필력 점검", slug="prose-audit")
    recipe = WritingRecipe(
        key="audit-recipe",
        version="1",
        name="감사 전개",
        recipe_json={"required_moves": ["ORIENT", "ANCHOR", "INTERPRET"]},
        is_builtin=True,
        approved=True,
    )
    db.add_all([project, recipe])
    db.flush()
    profile = VoiceProfile(
        project_id=project.id,
        key="audit-voice",
        version="1.0.0",
        name="감사 문체",
        description="절제",
        profile_json=voice_rules(),
        status="APPROVED",
    )
    db.add(profile)
    db.flush()
    example_text = "문이 닫혔다. 그는 손을 떼지 않았다. 복도의 공기가 조금씩 식었다."
    example = VoiceProfileExample(
        voice_profile_id=profile.id,
        label="겹침 검사",
        excerpt=example_text,
        teaches_json=[],
        scene_tags=["대치"],
        rights_basis="SELF_AUTHORED",
        use_in_generation=True,
        position=0,
        status="ACTIVE",
        excerpt_hash="hash",
    )
    session = PlaybookSession(
        project_id=project.id,
        writing_recipe_id=recipe.id,
        voice_profile_id=profile.id,
        voice_selection_mode="profile_default",
    )
    db.add_all([example, session])
    db.flush()
    document = LoreDocument(project_id=project.id, session_id=session.id, title="점검 원고")
    db.add(document)
    db.flush()
    block = LoreBlock(
        document_id=document.id,
        position=0,
        content_markdown=f"그는 매우 슬펐다. {example_text}",
    )
    db.add(block)
    db.commit()

    findings = run_prose_audits(db, document, voice_profile=profile)
    codes = {finding.code for finding in findings}
    assert "PROFILE_CONFLICT" in codes
    assert "REFERENCE_OVERLAP" in codes
    assert prose_document_hash(block.content_markdown) == prose_document_hash(block.content_markdown)
    db.close()
