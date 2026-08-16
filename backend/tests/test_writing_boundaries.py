import json

from conftest import isolated_session
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.api.router as router_module
from app.db import get_db
from app.main import app
from app.models import ConceptPage, GenerationRun
from app.services.model_gateway import ModelCallResult


class BoundaryGateway:
    def __init__(self) -> None:
        self.payload: dict = {}

    async def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        self.payload = json.loads(messages[1]["content"])
        content = json.dumps(
            {
                "locked_facts": [
                    {"text": "성문은 해질녘 닫힌다.", "source_excerpt": "성문은 해질녘 닫혔다"}
                ],
                "open_questions": [
                    {
                        "text": "수호자의 정체는 아직 공개하지 않는다.",
                        "source_excerpt": "수호자의 얼굴은 보이지 않았다",
                    }
                ],
                "forbidden_changes": [
                    {
                        "text": "해질 뒤 성문을 열지 않는다.",
                        "source_excerpt": "해질 뒤에는 누구도 열 수 없다",
                    }
                ],
            },
            ensure_ascii=False,
        )
        return ModelCallResult(
            content=content,
            role="utility",
            model="utility-test",
            endpoint="http://models.test/v1",
            params={"response_format": kwargs["response_mode"]},
            usage={"total_tokens": 42},
        )


def test_body_boundary_suggestion_requires_review_before_persistence(monkeypatch) -> None:
    db = isolated_session()

    def override_db():  # type: ignore[no-untyped-def]
        yield db

    gateway = BoundaryGateway()
    monkeypatch.setattr(router_module.harness, "gateway", gateway)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        project = client.post(
            "/api/v1/projects", json={"name": "경계 제안", "slug": "boundary-suggestion"}
        ).json()
        category = client.get(
            "/api/v1/categories", params={"project_id": project["id"]}
        ).json()[0]
        page = client.post(
            "/api/v1/concept-pages",
            json={
                "project_id": project["id"],
                "title": "해질의 성문",
                "category_key": category["key"],
                "body_json": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "저장된 예전 본문"}],
                        }
                    ],
                },
            },
        ).json()
        current_body = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "성문은 해질녘 닫혔다. 수호자의 얼굴은 보이지 않았다. 해질 뒤에는 누구도 열 수 없다.",
                        }
                    ],
                }
            ],
        }

        response = client.post(
            f"/api/v1/concept-pages/{page['id']}/suggest-writing-boundaries",
            json={"body_json": current_body, "locked_facts": ["현재 편집 중인 사실"]},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["persisted"] is False
        assert result["suggestion"]["locked_facts"][0]["text"] == "성문은 해질녘 닫힌다."
        assert gateway.payload["body"].startswith("성문은 해질녘")
        assert "저장된 예전 본문" not in gateway.payload["body"]
        assert gateway.payload["existing_boundaries"]["locked_facts"] == ["현재 편집 중인 사실"]

        stored_page = db.get(ConceptPage, page["id"])
        assert stored_page is not None
        assert stored_page.locked_facts == []
        assert stored_page.open_questions == []
        assert stored_page.forbidden_changes == []
        run = db.scalar(
            select(GenerationRun).where(GenerationRun.task == "writing_boundary_suggestion")
        )
        assert run is not None
        assert run.selected_concept_ids == [page["id"]]
        assert run.input_json["body"].startswith("성문은 해질녘")
    finally:
        app.dependency_overrides.clear()
        db.close()
