from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from app.config import ModelRole, settings

ResponseMode = Literal["text", "json_object", "json_schema"]


class ModelGatewayError(RuntimeError):
    def __init__(self, message: str, *, code: str = "MODEL_REQUEST_FAILED", role: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.role = role


@dataclass(frozen=True)
class ModelProfile:
    role: ModelRole
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int
    context_budget: int

    @classmethod
    def from_settings(cls, role: ModelRole) -> "ModelProfile":
        return cls(**settings.model_profile(role))  # type: ignore[arg-type]


@dataclass
class ModelCallResult:
    content: str
    role: str
    model: str
    endpoint: str
    params: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)
    timings: dict[str, Any] = field(default_factory=dict)
    fallback_from: str | None = None

    def audit_metadata(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "model": self.model,
            "endpoint": self.endpoint,
            "sampling": self.params,
            "usage": self.usage,
            "timings": self.timings,
            "fallback_from": self.fallback_from,
        }


class ModelGateway:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    def profile(self, role: ModelRole) -> ModelProfile:
        return ModelProfile.from_settings(role)

    def _client(self, profile: ModelProfile) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(profile.timeout_seconds),
            transport=self.transport,
        )

    @staticmethod
    def _headers(profile: ModelProfile) -> dict[str, str]:
        return {"Authorization": f"Bearer {profile.api_key}"} if profile.api_key else {}

    async def list_models(self, role: ModelRole) -> list[dict[str, Any]]:
        profile = self.profile(role)
        if not profile.base_url:
            raise ModelGatewayError(
                f"{role} 모델 엔드포인트가 설정되지 않았습니다.",
                code="MODEL_PROFILE_NOT_CONFIGURED",
                role=role,
            )
        try:
            async with self._client(profile) as client:
                response = await client.get(
                    f"{profile.base_url.rstrip('/')}/models",
                    headers=self._headers(profile),
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelGatewayError(
                f"{role} 모델 서버의 /v1/models 확인에 실패했습니다: {exc}",
                code="MODEL_HEALTH_FAILED",
                role=role,
            ) from exc
        models = data.get("data", []) if isinstance(data, dict) else []
        return [item for item in models if isinstance(item, dict)]

    async def resolve_model(self, profile: ModelProfile) -> tuple[str, dict[str, Any]]:
        models = await self.list_models(profile.role)
        if profile.model:
            match = next((item for item in models if item.get("id") == profile.model), None)
            if match is None and profile.role == "embedding":
                normalized = profile.model.lower().replace("_", "-")
                match = next(
                    (
                        item
                        for item in models
                        if str(item.get("id", "")).lower().replace("_", "-").startswith(normalized)
                    ),
                    None,
                )
            if match is None:
                available = ", ".join(str(item.get("id", "")) for item in models[:8]) or "없음"
                raise ModelGatewayError(
                    f"{profile.role} 모델 '{profile.model}'을 서버에서 찾을 수 없습니다. 사용 가능: {available}",
                    code="MODEL_NOT_FOUND",
                    role=profile.role,
                )
            return profile.model, match
        loaded = next(
            (
                item
                for item in models
                if not isinstance(item.get("status"), dict)
                or item.get("status", {}).get("value") in {None, "loaded"}
            ),
            None,
        )
        if loaded is None or not loaded.get("id"):
            raise ModelGatewayError(
                f"{profile.role} 프로필에서 자동 선택할 로드된 모델이 없습니다.",
                code="MODEL_NOT_FOUND",
                role=profile.role,
            )
        return str(loaded["id"]), loaded

    @staticmethod
    def _capabilities(model_info: dict[str, Any]) -> dict[str, Any]:
        architecture = model_info.get("architecture", {})
        input_modalities = architecture.get("input_modalities", ["text"])
        return {
            "chat": True,
            "streaming": True,
            "json_object": True,
            "json_schema": True,
            "vision": "image" in input_modalities,
            "input_modalities": input_modalities,
            "context_size": model_info.get("meta", {}).get("n_ctx"),
        }

    async def health(self, role: ModelRole) -> dict[str, Any]:
        profile = self.profile(role)
        try:
            model, info = await self.resolve_model(profile)
            return {
                "role": role,
                "available": True,
                "model": model,
                "capabilities": self._capabilities(info),
                "error": None,
            }
        except ModelGatewayError as exc:
            return {
                "role": role,
                "available": False,
                "model": profile.model,
                "capabilities": {},
                "error": {"code": exc.code, "message": str(exc)},
            }

    async def health_all(self) -> list[dict[str, Any]]:
        roles: list[ModelRole] = ["writer", "utility", "vision"]
        if settings.embedding_enabled:
            roles.append("embedding")
        return list(await asyncio.gather(*(self.health(role) for role in roles)))

    async def _post_completion(
        self,
        profile: ModelProfile,
        payload: dict[str, Any],
    ) -> ModelCallResult:
        last_error: Exception | None = None
        attempts = settings.model_retry_attempts + 1
        for attempt in range(attempts):
            try:
                async with self._client(profile) as client:
                    response = await client.post(
                        f"{profile.base_url.rstrip('/')}/chat/completions",
                        json=payload,
                        headers=self._headers(profile),
                    )
                    response.raise_for_status()
                    data = response.json()
                choice = data["choices"][0]
                content = choice["message"]["content"]
                if not isinstance(content, str):
                    raise ValueError("message.content가 문자열이 아닙니다.")
                return ModelCallResult(
                    content=content,
                    role=profile.role,
                    model=str(data.get("model") or payload["model"]),
                    endpoint=profile.base_url,
                    params={
                        key: value
                        for key, value in payload.items()
                        if key not in {"messages", "model"}
                    },
                    usage=data.get("usage", {}),
                    timings=data.get("timings", {}),
                )
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.25 * (2**attempt))
        raise ModelGatewayError(
            f"{profile.role} 모델 서버 호출이 {attempts}회 실패했습니다: {last_error}",
            code="MODEL_REQUEST_FAILED",
            role=profile.role,
        ) from last_error

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        role: ModelRole = "writer",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_mode: ResponseMode = "text",
        json_schema: dict[str, Any] | None = None,
        schema_name: str = "lore_studio_response",
        seed: int | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> ModelCallResult:
        profile = self.profile(role)
        model, _ = await self.resolve_model(profile)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if seed is not None:
            payload["seed"] = seed
        if response_mode == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif response_mode == "json_schema":
            if not json_schema:
                raise ValueError("json_schema 응답에는 스키마가 필요합니다.")
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": json_schema, "strict": True},
            }
        if extra_params:
            payload.update(extra_params)
        try:
            return await self._post_completion(profile, payload)
        except ModelGatewayError:
            if role != "utility" or not settings.allow_utility_writer_fallback:
                raise
            writer = self.profile("writer")
            writer_model, _ = await self.resolve_model(writer)
            fallback_payload = dict(payload, model=writer_model)
            result = await self._post_completion(writer, fallback_payload)
            result.fallback_from = "utility"
            return result

    async def stream_complete(
        self,
        messages: list[dict[str, Any]],
        *,
        role: ModelRole = "writer",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        seed: int | None = None,
    ) -> AsyncIterator[str]:
        profile = self.profile(role)
        model, _ = await self.resolve_model(profile)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if seed is not None:
            payload["seed"] = seed
        try:
            async with self._client(profile) as client:
                async with client.stream(
                    "POST",
                    f"{profile.base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=self._headers(profile),
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:]
                        if raw == "[DONE]":
                            break
                        data = json.loads(raw)
                        delta = data.get("choices", [{}])[0].get("delta", {}).get("content")
                        if isinstance(delta, str) and delta:
                            yield delta
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            raise ModelGatewayError(
                f"{role} 스트리밍 생성 중 연결이 끊겼습니다: {exc}",
                code="MODEL_STREAM_FAILED",
                role=role,
            ) from exc

    async def embed(self, texts: list[str]) -> tuple[list[list[float]], dict[str, Any]]:
        if not settings.embedding_enabled:
            raise ModelGatewayError(
                "임베딩이 비활성화되어 있습니다.",
                code="EMBEDDING_DISABLED",
                role="embedding",
            )
        profile = self.profile("embedding")
        model, _ = await self.resolve_model(profile)
        payload = {"model": model, "input": texts}
        try:
            async with self._client(profile) as client:
                response = await client.post(
                    f"{profile.base_url.rstrip('/')}/embeddings",
                    json=payload,
                    headers=self._headers(profile),
                )
                response.raise_for_status()
                data = response.json()
            rows = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
            embeddings = [row["embedding"] for row in rows]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ModelGatewayError(
                f"임베딩 서버 호출에 실패했습니다: {exc}",
                code="EMBEDDING_REQUEST_FAILED",
                role="embedding",
            ) from exc
        if len(embeddings) != len(texts):
            raise ModelGatewayError(
                "임베딩 응답 개수가 요청과 다릅니다.",
                code="EMBEDDING_COUNT_MISMATCH",
                role="embedding",
            )
        dimensions = {len(vector) for vector in embeddings}
        if dimensions and dimensions != {settings.embedding_dimension}:
            actual = ", ".join(str(value) for value in sorted(dimensions))
            raise ModelGatewayError(
                f"임베딩 차원이 설정({settings.embedding_dimension})과 다릅니다: {actual}",
                code="EMBEDDING_DIMENSION_MISMATCH",
                role="embedding",
            )
        return embeddings, {
            "role": "embedding",
            "model": str(data.get("model") or model),
            "endpoint": profile.base_url,
            "usage": data.get("usage", {}),
            "dimension": settings.embedding_dimension,
            "version": settings.embedding_version,
        }
