from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

ModelConnectionRole = Literal["writer", "utility", "vision"]


class ModelConnectionUpdate(BaseModel):
    base_url: str = Field(min_length=8, max_length=2048)
    model: str = Field(default="", max_length=300)
    api_key: str | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False
    timeout_seconds: int = Field(ge=1, le=3600)
    context_budget: int = Field(ge=1024, le=1_000_000)
    disable_thinking: bool = False

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Base URL은 http:// 또는 https:// 주소여야 합니다.")
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("Base URL에 인증 정보·query·fragment를 넣지 마세요.")
        return normalized

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        return value.strip()


class ModelConnectionTest(ModelConnectionUpdate):
    role: ModelConnectionRole


class ModelConnectionRead(BaseModel):
    role: ModelConnectionRole
    base_url: str
    model: str
    timeout_seconds: int
    context_budget: int
    disable_thinking: bool
    api_key_configured: bool
    source: Literal["environment", "database"]


class ModelConnectionTestRead(BaseModel):
    role: ModelConnectionRole
    available: bool
    model: str
    models: list[str]
    capabilities: dict[str, object]
    error: dict[str, str] | None = None
