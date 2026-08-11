import asyncio

import httpx
import pytest
from conftest import HandlerTransport, isolated_session
from pydantic import ValidationError

from app.api import model_connections as routes
from app.model_connection_schemas import ModelConnectionTest, ModelConnectionUpdate
from app.models import AuditLog, ModelConnectionSetting
from app.services.model_connections import clear_model_connection_override


def _payload(**overrides) -> ModelConnectionUpdate:
    values = {
        "base_url": "http://models.test/v1",
        "model": "qwen-test",
        "api_key": "secret-value",
        "timeout_seconds": 300,
        "context_budget": 32768,
        "disable_thinking": True,
    }
    values.update(overrides)
    return ModelConnectionUpdate(**values)


def test_model_connection_save_masks_key_and_reset_restores_environment(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret-value"
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "qwen-test"}]})
        payload = request.read()
        assert b'"enable_thinking":false' in payload
        return httpx.Response(
            200,
            json={"model": "qwen-test", "choices": [{"message": {"content": "ok"}}]},
        )

    monkeypatch.setattr(routes.gateway, "transport", HandlerTransport(handler))
    db = isolated_session()
    try:
        saved = asyncio.run(routes.update_model_connection("writer", _payload(), db))
        assert saved["source"] == "database"
        assert saved["api_key_configured"] is True
        assert saved["disable_thinking"] is True
        assert "secret-value" not in str(saved)
        row = db.get(ModelConnectionSetting, "writer")
        assert row is not None and row.api_key == "secret-value"
        audit = db.query(AuditLog).filter_by(action="MODEL_CONNECTION_UPDATED").one()
        assert "secret-value" not in str(audit.after_json)

        result = asyncio.run(routes.gateway.complete([{"role": "user", "content": "짧게"}]))
        assert result.content == "ok"

        reset = routes.reset_model_connection("writer", db)
        assert reset["source"] == "environment"
        assert db.get(ModelConnectionSetting, "writer") is None
    finally:
        clear_model_connection_override("writer")
        db.close()


def test_connection_test_does_not_persist(monkeypatch) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "qwen-test"}]})

    monkeypatch.setattr(routes.gateway, "transport", HandlerTransport(handler))
    payload = ModelConnectionTest(role="vision", **_payload().model_dump())
    result = asyncio.run(routes.test_model_connection(payload))
    assert result["available"] is True
    assert result["models"] == ["qwen-test"]


def test_connection_url_rejects_embedded_credentials() -> None:
    with pytest.raises(ValidationError):
        _payload(base_url="http://user:pass@models.test/v1")
