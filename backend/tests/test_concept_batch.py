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
from app.models import ConceptPage, GenerationRun
from app.schemas import ConceptBatchGenerateRequest
from app.services.concept_batch import BatchContext, _generate_one, _parse_object, propose_seeds
from app.services.model_gateway import ModelCallResult, ModelGatewayError, ModelProfile


class BatchGateway:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.worker_calls = 0
        self.fail_titles: set[str] = set()
        self.payloads: list[dict] = []

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
        self.payloads.append(payload)
        if kwargs["schema_name"] == "concept_seed_list":
            count = payload["requested_seed_count"]
            content = {
                "seeds": [
                    {
                        "title": f"성역의 음식 {index}",
                        "summary": f"성역의 사건과 풍토에서 비롯된 음식 씨앗 {index}.",
                        "distinction": f"지역 {index}의 계층과 재료를 함께 드러낸다.",
                        "source_basis": ["악마의 침공 이후에도 풍습을 지켰다."],
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
            body = (
                f"{seed['title']}의 유래다.\n\n"
                + "사람들은 의식 때 이 음식을 나누며 지역의 기억과 생활 규칙을 확인한다. " * 9
            ).strip()
            content = {
                "title": seed["title"],
                "summary": seed["summary"],
                "content_text": body,
                "tags": ["음식", "성역"],
                "warnings": [],
                "details": [
                    {"label": "사회적 용도", "value": "의식 때 공동체가 나누어 먹는다."}
                ],
                "inherited_facts": ["악마의 침공 이후에도 지역 풍습이 이어진다."],
                "candidate_facts": ["이 음식은 의식 때 나눈다."],
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
        assert gateway.payloads[0]["target_material_type"]["writing_blueprint"] == [
            "재료와 조리",
            "먹는 지역·계층",
            "사회적 용도",
            "희소성·금기",
            "지역별 변형",
        ]

        selected = seed_data["seeds"][:3]
        selected[0]["summary"] = "사용자가 조금 다듬은 첫 번째 씨앗"
        generated_response = client.post(
            "/api/v1/concept-batches/generate",
            json={
                "seed_run_id": seed_data["run_id"],
                "selected_seeds": selected,
                "writer_model_key": "gemma",
                "length_key": "brief",
                "max_concurrency": 2,
            },
        )
        assert generated_response.status_code == 200
        generated = generated_response.json()
        assert generated["requested_count"] == 3
        assert len(generated["candidates"]) == 3
        assert generated["failures"] == []
        assert gateway.worker_calls == 3
        assert gateway.max_active == 2
        assert generated["writer_model_key"] == "gemma"
        assert generated["length_key"] == "brief"
        assert generated["max_concurrency"] == 2
        assert generated["candidates"][0]["details"][0]["label"] == "사회적 용도"
        assert generated["candidates"][0]["character_count"] > 0
        assert gateway.payloads[1]["length_contract"] == {
            "label": "간단",
            "minimum_characters": 500,
            "target_characters": 700,
            "maximum_characters": 1000,
        }

        gateway.fail_titles.add(seed_data["seeds"][3]["title"])
        partial_response = client.post(
            "/api/v1/concept-batches/generate",
            json={
                "seed_run_id": seed_data["run_id"],
                "selected_seeds": seed_data["seeds"][3:5],
                "max_concurrency": 1,
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
        assert accepted[0]["properties_json"]["batch_generation"]["writer_model_key"] == "gemma"
        assert accepted[0]["properties_json"]["batch_generation"]["details"][0]["label"] == "사회적 용도"
        assert "권장 분량" in accepted[0]["properties_json"]["batch_generation"]["warnings"][0]

        duplicate = client.post(
            "/api/v1/concept-batches/accept",
            json={"seed_run_id": seed_data["run_id"], "candidates": chosen[:1]},
        )
        assert duplicate.status_code == 409

        runs = list(db.scalars(select(GenerationRun)).all())
        assert [run.task for run in runs].count("concept_batch_seed_planning") == 1
        assert [run.task for run in runs].count("concept_batch_worker") == 5
        assert [run.status for run in runs].count("failed") == 1
        assert next(run for run in runs if run.task == "concept_batch_seed_planning").prompt_components == {
            "concept_batch": "seed_planning_v2"
        }
        assert all(
            run.prompt_components == {"concept_batch": "candidate_writer_v2"}
            for run in runs
            if run.task == "concept_batch_worker"
        )
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


def test_model_object_parser_reads_first_complete_object_with_wrappers() -> None:
    content = '```json\n{"value":"첫줄\n둘째 줄"}\n```\n검토 메모 {"ignored":true}'

    assert _parse_object(content, code="TEST") == {"value": "첫줄\n둘째 줄"}


def test_candidate_writer_revises_short_or_internal_marker_content() -> None:
    class RevisionGateway:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def complete_for_profile(self, profile, messages, **kwargs):  # type: ignore[no-untyped-def]
            schema_name = kwargs["schema_name"]
            self.calls.append(schema_name)
            if schema_name == "concept_batch_candidate":
                body = "[후보 설정: 화덕의 재가 음식에 쓰인다.] candidate_fact: 검토 필요"
            else:
                body = (
                    "공동 화덕을 쓰는 주민들은 정해진 시간에 재료를 손질하고 서로의 순서를 지킨다. "
                    "이 과정은 열원이 부족한 항구에서 식사를 준비하는 생활 규칙과 계층 차이를 보여 준다. "
                    * 18
                ).strip()
            content = {
                "title": "화덕의 음식",
                "summary": "공동 화덕에서 비롯된 항구의 식문화.",
                "content_text": body,
                "tags": ["음식"],
                "warnings": [],
                "details": [{"label": "사회적 용도", "value": "공동 식사"}],
                "inherited_facts": ["공동 화덕이 있다."],
                "candidate_facts": ["새 음식의 이름은 미정이다."],
            }
            return ModelCallResult(
                content=json.dumps(content, ensure_ascii=False),
                role=profile.role,
                model=profile.model,
                endpoint=profile.base_url,
                params={"schema_name": schema_name},
                usage={"total_tokens": 100},
            )

    gateway = RevisionGateway()
    profile = ModelProfile(
        role="writer",
        base_url="http://writer.test/v1",
        api_key="test",
        model="gemma-test",
        timeout_seconds=30,
        context_budget=24_000,
    )
    context = BatchContext(
        project_id="project",
        source_page_id="source",
        source_title="항구 이야기",
        source_summary="열원이 부족한 항구다.",
        source_body="주민들은 공동 화덕을 사용한다.",
        source_boundaries={"locked_facts": ["공동 화덕이 있다."], "open_questions": [], "forbidden_changes": []},
        namespace="",
        era="",
        continuity="",
        category_key="food",
        category_name="음식",
        category_description="항구의 음식과 식문화",
        category_template={},
        existing_titles=[],
        additional_instruction="",
    )
    candidate, result = asyncio.run(
        _generate_one(
            gateway,
            profile=profile,
            context=context,
            seed={
                "seed_id": "seed-1",
                "title": "화덕의 음식",
                "summary": "공동 화덕 음식",
                "distinction": "열원 제약",
                "source_basis": ["공동 화덕이 있다."],
            },
            length_key="standard",
        )
    )

    assert gateway.calls == ["concept_batch_candidate", "concept_batch_candidate_revision"]
    assert "candidate_fact" not in candidate["content_text"]
    assert "[후보 설정" not in candidate["content_text"]
    assert candidate["character_count"] >= 1000
    assert result.usage["total_tokens"] == 200
    assert result.params["automatic_revisions"]["attempts"] == 1


def test_seed_planner_retries_invalid_structured_response_once() -> None:
    class SeedRevisionGateway:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def complete_for_profile(self, profile, messages, **kwargs):  # type: ignore[no-untyped-def]
            schema_name = kwargs["schema_name"]
            self.calls.append(schema_name)
            if schema_name == "concept_seed_list":
                content = "{"
            else:
                content = json.dumps(
                    {
                        "seeds": [
                            {
                                "title": f"항구 음식 {index}",
                                "summary": f"공동 화덕에서 비롯된 음식 {index}.",
                                "distinction": f"열원 제약의 다른 양상 {index}.",
                                "source_basis": ["주민들은 공동 화덕을 사용한다."],
                            }
                            for index in range(1, 7)
                        ]
                    },
                    ensure_ascii=False,
                )
            return ModelCallResult(
                content=content,
                role=profile.role,
                model=profile.model,
                endpoint=profile.base_url,
                params={"schema_name": schema_name},
                usage={"total_tokens": 50},
            )

    gateway = SeedRevisionGateway()
    profile = ModelProfile(
        role="utility",
        base_url="http://utility.test/v1",
        api_key="test",
        model="qwen-test",
        timeout_seconds=30,
        context_budget=24_000,
        disable_thinking=True,
    )
    context = BatchContext(
        project_id="project",
        source_page_id="source",
        source_title="항구 이야기",
        source_summary="열원이 부족한 항구다.",
        source_body="주민들은 공동 화덕을 사용한다.",
        source_boundaries={"locked_facts": [], "open_questions": [], "forbidden_changes": []},
        namespace="",
        era="",
        continuity="",
        category_key="food",
        category_name="음식",
        category_description="항구의 음식과 식문화",
        category_template={},
        existing_titles=[],
        additional_instruction="",
    )

    seeds, result = asyncio.run(
        propose_seeds(gateway, profile=profile, context=context, seed_count=6)
    )

    assert len(seeds) == 6
    assert gateway.calls == ["concept_seed_list", "concept_seed_list_revision"]
    assert result.usage["total_tokens"] == 100
    assert result.params["automatic_revisions"] == {
        "attempts": 1,
        "reasons": ["CONCEPT_SEED_RESPONSE_INVALID"],
    }
