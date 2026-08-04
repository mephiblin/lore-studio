import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.services.model_gateway import ModelGateway, ModelGatewayError


def test_utility_profile_resolves_model_and_records_call(monkeypatch) -> None:
    monkeypatch.setattr(settings, "utility_model_base_url", "http://models.test/v1")
    monkeypatch.setattr(settings, "utility_model_name", "utility-test")
    monkeypatch.setattr(settings, "model_retry_attempts", 0)

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "utility-test"}]})
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "model": "utility-test",
                "choices": [{"message": {"content": '{"status":"ok"}'}}],
                "usage": {"total_tokens": 12},
            },
        )

    gateway = ModelGateway(transport=httpx.MockTransport(handler))
    result = asyncio.run(
        gateway.complete(
            [{"role": "user", "content": "구조화"}],
            role="utility",
            response_mode="json_object",
            temperature=0,
        )
    )

    assert result.content == '{"status":"ok"}'
    assert result.role == "utility"
    assert result.model == "utility-test"
    assert result.audit_metadata()["usage"]["total_tokens"] == 12


def test_embedding_dimension_mismatch_stops_indexing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_enabled", True)
    monkeypatch.setattr(settings, "embedding_base_url", "http://embedding.test/v1")
    monkeypatch.setattr(settings, "embedding_model", "bge-test")
    monkeypatch.setattr(settings, "embedding_dimension", 3)

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "bge-test"}]})
        return httpx.Response(
            200,
            json={"model": "bge-test", "data": [{"index": 0, "embedding": [0.1, 0.2]}]},
        )

    gateway = ModelGateway(transport=httpx.MockTransport(handler))
    with pytest.raises(ModelGatewayError) as error:
        asyncio.run(gateway.embed(["차원 불일치"] ))
    assert error.value.code == "EMBEDDING_DIMENSION_MISMATCH"


def test_mock_mode_never_contacts_external_model(monkeypatch) -> None:
    monkeypatch.setattr(settings, "mock_model", True)
    monkeypatch.setattr(settings, "embedding_enabled", True)
    monkeypatch.setattr(settings, "embedding_dimension", 4)
    gateway = ModelGateway(
        transport=httpx.MockTransport(lambda request: pytest.fail(f"unexpected request: {request.url}"))
    )

    health = asyncio.run(gateway.health("writer"))
    result = asyncio.run(
        gateway.complete(
            [{"role": "user", "content": "구조화"}],
            role="utility",
            response_mode="json_schema",
            json_schema={"type": "object"},
            schema_name="direction_card_rules",
        )
    )
    vectors, metadata = asyncio.run(gateway.embed(["격리 테스트"]))

    assert health["model"] == "mock"
    assert json.loads(result.content)["sequence"] == ["효능", "의존", "대가"]
    assert vectors == [[0.0, 0.0, 0.0, 0.0]]
    assert metadata["endpoint"] == ""
