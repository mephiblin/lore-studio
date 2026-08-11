import json

from conftest import isolated_session
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.api.router as router_module
from app.db import get_db
from app.main import app
from app.models import ConceptPage, GenerationRun
from app.services.model_gateway import ModelCallResult


class ConceptAiGateway:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def complete_for_profile(self, profile, messages, **kwargs):  # type: ignore[no-untyped-def]
        payload = json.loads(messages[1]["content"])
        self.calls.append({"profile": profile, "payload": payload, "kwargs": kwargs})
        is_rewrite = payload["task"] == "rewrite_selection"
        content_text = (
            "성문은 해가 지기 전에 닫히며, 수호자는 침묵으로 통행을 막는다."
            if is_rewrite
            else "## 해질의 성문\n\n성문은 저녁마다 닫힌다.\n\n> 수호자의 정체는 아직 드러나지 않는다."
        )
        response = {"content_text": content_text, "warnings": ["사용자 검토가 필요합니다."]}
        if is_rewrite:
            response.update(
                {
                    "context_summary": "해질 무렵 성문과 수호자를 설명하는 세계관 자료다.",
                    "continuity_requirements": ["뒤 문장의 수호자 언급으로 자연스럽게 이어진다."],
                }
            )
        return ModelCallResult(
            content=json.dumps(response, ensure_ascii=False),
            role=profile.role,
            model=profile.model,
            endpoint=profile.base_url,
            params={"response_format": kwargs["response_mode"]},
            usage={"total_tokens": 73},
        )


def _paragraph(text: str) -> dict:
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def test_concept_ai_returns_reviewable_proposals_without_saving(monkeypatch) -> None:
    db = isolated_session()

    def override_db():  # type: ignore[no-untyped-def]
        yield db

    gateway = ConceptAiGateway()
    monkeypatch.setattr(router_module.harness, "gateway", gateway)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        project = client.post(
            "/api/v1/projects", json={"name": "AI 본문", "slug": "concept-ai"}
        ).json()
        category = client.get(
            "/api/v1/categories", params={"project_id": project["id"]}
        ).json()[0]
        current = client.post(
            "/api/v1/concept-pages",
            json={
                "project_id": project["id"],
                "title": "해질의 성문",
                "category_key": category["key"],
                "body_json": _paragraph("저장된 예전 본문"),
            },
        ).json()
        fact_source = client.post(
            "/api/v1/concept-pages",
            json={
                "project_id": project["id"],
                "title": "성문 규칙",
                "category_key": category["key"],
                "summary": "해질 전 폐문한다.",
                "body_json": _paragraph("해가 지면 성문은 열 수 없다."),
                "locked_facts": ["성문은 해질 전에 닫힌다."],
            },
        ).json()
        inspiration = client.post(
            "/api/v1/concept-pages",
            json={
                "project_id": project["id"],
                "title": "분위기 참고",
                "category_key": category["key"],
                "usage_role": "INSPIRATION",
                "summary": "고립감과 침묵의 분위기",
                "body_json": _paragraph("다른 작품의 고유한 성문 이름"),
            },
        ).json()
        unsaved_body = _paragraph("성문은 늦게 닫혔다. 수호자의 얼굴은 보이지 않았다.")

        rewrite = client.post(
            f"/api/v1/concept-pages/{current['id']}/ai/rewrite-selection",
            json={
                "body_json": unsaved_body,
                "model_key": "qwen",
                "selection_from": 0,
                "selection_to": 13,
                "selection_text": "성문은 늦게 닫혔다.",
                "operation": "longer",
                "source_page_ids": [fact_source["id"], inspiration["id"]],
                "open_questions": ["수호자의 정체는 아직 공개하지 않는다."],
            },
        )

        assert rewrite.status_code == 200
        proposal = rewrite.json()
        assert proposal["status"] == "CANDIDATE"
        assert proposal["persisted"] is False
        assert proposal["mode"] == "rewrite_selection"
        assert proposal["model_key"] == "qwen"
        assert proposal["selection_from"] == 0
        assert proposal["original_text"] == "성문은 늦게 닫혔다."
        assert proposal["proposed_text"].startswith("성문은 해가 지기 전에")
        assert proposal["source_page_ids"] == [fact_source["id"], inspiration["id"]]
        assert gateway.calls[0]["profile"].model == "qwen36-heretic-mtp"

        rewrite_payload = gateway.calls[0]["payload"]
        assert rewrite_payload["target"]["selection_text"] == "성문은 늦게 닫혔다."
        context = rewrite_payload["read_only_context"]
        assert context["current_page"]["body_context"]["text"].startswith("성문은 늦게")
        assert context["current_page"]["selection_context"]["found"] is True
        assert context["current_page"]["selection_context"]["after"].startswith(
            " 수호자의 얼굴은"
        )
        assert rewrite_payload["length_contract"]["mode"] == "expand_with_substance"
        assert rewrite_payload["length_contract"]["minimum_chars"] > len(
            rewrite_payload["target"]["selection_text"]
        )
        rewrite_schema = gateway.calls[0]["kwargs"]["json_schema"]
        assert rewrite_schema["properties"]["content_text"]["minLength"] == rewrite_payload[
            "length_contract"
        ]["minimum_chars"]
        assert gateway.calls[0]["kwargs"]["max_tokens"] >= 4200
        assert {"context_summary", "continuity_requirements"}.issubset(
            rewrite_schema["required"]
        )
        assert context["current_page"]["writing_boundaries"]["open_questions"] == [
            "수호자의 정체는 아직 공개하지 않는다."
        ]
        assert context["reference_material"]["fact_eligible"][0]["title"] == "성문 규칙"
        style_reference = context["reference_material"]["style_or_inspiration_only"][0]
        assert style_reference["fact_eligible"] is False
        assert style_reference["body_omitted"] is True
        assert "다른 작품의 고유한 성문 이름" not in json.dumps(context, ensure_ascii=False)

        draft = client.post(
            f"/api/v1/concept-pages/{current['id']}/ai/draft",
            json={
                "body_json": unsaved_body,
                "model_key": "gemma",
                "prompt": "폐문 절차를 설명하는 초안을 써 줘.",
                "source_page_ids": [fact_source["id"]],
                "placement": "append",
                "length": "short",
            },
        )
        assert draft.status_code == 200
        assert draft.json()["status"] == "CANDIDATE"
        assert draft.json()["persisted"] is False
        assert draft.json()["model_key"] == "gemma"
        assert draft.json()["proposed_text"].startswith("## 해질의 성문")
        assert gateway.calls[1]["payload"]["placement"] == "append"
        assert gateway.calls[1]["profile"].model == "gemma4-26b-heretic-mtp"

        stored = db.get(ConceptPage, current["id"])
        assert stored is not None
        assert stored.body_json == _paragraph("저장된 예전 본문")
        runs = list(
            db.scalars(
                select(GenerationRun).where(
                    GenerationRun.task.in_(["concept_selection_rewrite", "concept_body_draft"])
                )
            ).all()
        )
        assert {run.task for run in runs} == {"concept_selection_rewrite", "concept_body_draft"}
        assert all(run.input_hash for run in runs)
        assert all(run.selected_concept_ids[0] == current["id"] for run in runs)
        rewrite_run = next(run for run in runs if run.task == "concept_selection_rewrite")
        assert rewrite_run.prompt_components == {
            "concept_editor": "selection_contextual_rewrite_v3"
        }
        assert rewrite_run.model_role == "utility"
        assert rewrite_run.input_json["model_key"] == "qwen"
        assert rewrite_run.input_json["context"]["current_page"]["selection_context"][
            "found"
        ] is True
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_concept_ai_rejects_reference_from_another_project(monkeypatch) -> None:
    db = isolated_session()

    def override_db():  # type: ignore[no-untyped-def]
        yield db

    gateway = ConceptAiGateway()
    monkeypatch.setattr(router_module.harness, "gateway", gateway)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        first = client.post(
            "/api/v1/projects", json={"name": "첫 세계", "slug": "first-world"}
        ).json()
        second = client.post(
            "/api/v1/projects", json={"name": "둘째 세계", "slug": "second-world"}
        ).json()
        first_category = client.get(
            "/api/v1/categories", params={"project_id": first["id"]}
        ).json()[0]
        second_category = client.get(
            "/api/v1/categories", params={"project_id": second["id"]}
        ).json()[0]
        current = client.post(
            "/api/v1/concept-pages",
            json={
                "project_id": first["id"],
                "title": "첫 자료",
                "category_key": first_category["key"],
            },
        ).json()
        foreign = client.post(
            "/api/v1/concept-pages",
            json={
                "project_id": second["id"],
                "title": "외부 자료",
                "category_key": second_category["key"],
            },
        ).json()

        stale_selection = client.post(
            f"/api/v1/concept-pages/{current['id']}/ai/rewrite-selection",
            json={
                "body_json": _paragraph("현재 본문"),
                "selection_from": 1,
                "selection_to": 5,
                "selection_text": "본문에 없는 문장",
            },
        )
        assert stale_selection.status_code == 422
        assert stale_selection.json()["detail"]["code"] == "SELECTION_NOT_IN_BODY"

        response = client.post(
            f"/api/v1/concept-pages/{current['id']}/ai/draft",
            json={
                "body_json": _paragraph("현재 본문"),
                "prompt": "초안을 작성해 줘.",
                "source_page_ids": [foreign["id"]],
            },
        )

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "INVALID_AI_REFERENCE"
        assert gateway.calls == []
    finally:
        app.dependency_overrides.clear()
        db.close()
