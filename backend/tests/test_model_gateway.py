import asyncio
import json

import httpx
from conftest import HandlerTransport

from app.config import settings
from app.services.model_gateway import ModelGateway, local_text_profile


def test_both_selectable_local_models_disable_thinking() -> None:
    assert local_text_profile("qwen").disable_thinking is True
    assert local_text_profile("gemma").disable_thinking is True


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

    gateway = ModelGateway(transport=HandlerTransport(handler))
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
