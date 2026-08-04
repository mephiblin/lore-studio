from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class ModelGatewayError(RuntimeError):
    pass


class ModelGateway:
    def __init__(self) -> None:
        self.base_url = settings.model_base_url.rstrip("/")
        self.api_key = settings.model_api_key
        self.model = settings.model_name
        self.timeout = settings.model_timeout_seconds

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ModelGatewayError(f"로컬 모델 서버 호출 실패: {exc}") from exc

        data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelGatewayError("모델 서버 응답에서 message.content를 찾을 수 없습니다.") from exc
