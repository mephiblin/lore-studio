import asyncio
import json

import pytest
from conftest import isolated_session
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

import app.api.router as router_module
from app.db import get_db
from app.main import app
from app.models import ConceptPage, GenerationRun, IndexJob
from app.schemas import ConceptBatchGenerateRequest
from app.services.model_gateway import ModelCallResult, ModelGatewayError, ModelProfile


class BatchGateway:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.worker_calls = 0
        self.fail_titles: set[str] = set()

    def profile(self, role):  # type: ignore[no-untyped-def]
        return ModelProfile(
            role=role,
            base_url=f"http://{role}.test/v1",
            api_key="test",
            model="qwen-test" if role == "utility" else "gemma-test",
            timeout_seconds=30,
            context_budget=24_000,
            disable_thinking=role == "utility",
        )

    async def complete_for_profile(self, profile, messages, **kwargs):  # type: ignore[no-untyped-def]
        payload = json.loads(messages[1]["content"])
        if kwargs["schema_name"] == "concept_seed_list":
            count = payload["requested_seed_count"]
            content = {
                "seeds": [
                    {
                        "title": f"성역의 음식 {index}",
                        "summary": f"성역의 사건과 풍토에서 비롯된 음식 씨앗 {index}.",
                    }
                    for index in range(1, count + 1)
                ]
            }
        else:
            self.worker_calls += 1
            seed = payload["selected_seed"]
            if seed["title"] in self.fail_titles:
                raise ModelGatewayError("의도한 worker 실패", code="TEST_WORKER_FAILED")
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.03)
            self.active -= 1
            content = {
                "title": seed["title"],
                "summary": seed["summary"],
                "content_text": f"{seed['title']}의 유래다.\n\n사람들은 의식 때 이 음식을 나눈다.",
                "tags": ["음식", "성역"],
                "warnings": [],
            }
        return ModelCallResult(
            content=json.dumps(content, ensure_ascii=False),
            role=profile.role,
            model=profile.model,
            endpoint=profile.base_url,
            params={"schema_name": kwargs["schema_name"]},
            usage={"total_tokens": 100},
        )


def _paragraph(text: str) -> dict:
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def test_seed_selection_drives_parallel_candidate_generation_and_explicit_save(
    monkeypatch,
) -> None:
    db = isolated_session()

    def override_db():  # type: ignore[no-untyped-def]
        yield db

    gateway = BatchGateway()
    monkeypatch.setattr(router_module.harness, "gateway", gateway)
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        project = client.post("/api/v1/projects", json={"name": "성역", "slug": "sanctuary-batch"}).json()
        category = client.post(
            "/api/v1/categories",
            json={
                "project_id": project["id"],
                "name": "음식",
                "description": "세계관 안에서 먹는 음식과 식문화",
            },
        ).json()
        source = client.post(
            "/api/v1/concept-pages",
            json={
                "project_id": project["id"],
                "title": "성역의 이야기",
                "category_key": category["key"],
                "body_json": _paragraph("성역은 악마의 침공 이후에도 각 지역의 풍습을 지켰다."),
                "locked_facts": ["악마의 침공이 있었다."],
            },
        ).json()

        seed_response = client.post(
            "/api/v1/concept-batches/seeds",
            json={
                "project_id": project["id"],
                "source_page_id": source["id"],
                "category_key": category["key"],
                "model_key": "gemma",
                "seed_count": 6,
                "additional_instruction": "지역별 재료 차이를 드러내 줘.",
            },
        )
        assert seed_response.status_code == 200
        seed_data = seed_response.json()
        assert len(seed_data["seeds"]) == 6
        assert seed_data["seeds"][0]["seed_id"] == "seed-1"

        selected = seed_data["seeds"][:3]
        selected[0]["summary"] = "사용자가 조금 다듬은 첫 번째 씨앗"
        generated_response = client.post(
            "/api/v1/concept-batches/generate",
            json={"seed_run_id": seed_data["run_id"], "selected_seeds": selected},
        )
        assert generated_response.status_code == 200
        generated = generated_response.json()
        assert generated["requested_count"] == 3
        assert len(generated["candidates"]) == 3
        assert generated["failures"] == []
        assert gateway.worker_calls == 3
        assert gateway.max_active == 3

        gateway.fail_titles.add(seed_data["seeds"][3]["title"])
        partial_response = client.post(
            "/api/v1/concept-batches/generate",
            json={
                "seed_run_id": seed_data["run_id"],
                "selected_seeds": seed_data["seeds"][3:5],
            },
        )
        assert partial_response.status_code == 200
        partial = partial_response.json()
        assert len(partial["candidates"]) == 1
        assert partial["failures"] == [
            {
                "seed_id": "seed-4",
                "title": "성역의 음식 4",
                "code": "TEST_WORKER_FAILED",
                "message": "의도한 worker 실패",
            }
        ]

        before_accept = client.get("/api/v1/concept-pages", params={"project_id": project["id"]}).json()
        assert [page["id"] for page in before_accept] == [source["id"]]

        chosen = [
            {
                "run_id": candidate["run_id"],
                "title": candidate["title"],
                "summary": candidate["summary"],
                "content_text": candidate["content_text"],
                "tags": candidate["tags"],
            }
            for candidate in generated["candidates"][:2]
        ]
        accepted_response = client.post(
            "/api/v1/concept-batches/accept",
            json={"seed_run_id": seed_data["run_id"], "candidates": chosen},
        )
        assert accepted_response.status_code == 201
        accepted = accepted_response.json()
        assert len(accepted) == 2
        assert {page["usage_role"] for page in accepted} == {"CANDIDATE"}
        assert {page["authority_state"] for page in accepted} == {"CANDIDATE"}
        assert {page["category_key"] for page in accepted} == {category["key"]}
        assert all(
            page["properties_json"]["batch_generation"]["source_page_id"] == source["id"] for page in accepted
        )

        duplicate = client.post(
            "/api/v1/concept-batches/accept",
            json={"seed_run_id": seed_data["run_id"], "candidates": chosen[:1]},
        )
        assert duplicate.status_code == 409

        runs = list(db.scalars(select(GenerationRun)).all())
        assert [run.task for run in runs].count("concept_batch_seed_planning") == 1
        assert [run.task for run in runs].count("concept_batch_worker") == 5
        assert [run.status for run in runs].count("failed") == 1
        assert db.scalar(select(IndexJob).where(IndexJob.concept_page_id == accepted[0]["id"]))
        stored = db.get(ConceptPage, accepted[0]["id"])
        assert stored is not None
        assert stored.body_json["type"] == "doc"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_batch_rejects_more_than_ten_selected_seeds() -> None:
    with pytest.raises(ValidationError):
        ConceptBatchGenerateRequest.model_validate(
            {
                "seed_run_id": "missing",
                "selected_seeds": [
                    {
                        "seed_id": f"seed-{index}",
                        "title": f"씨앗 {index}",
                        "summary": "내용",
                    }
                    for index in range(1, 12)
                ],
            }
        )
