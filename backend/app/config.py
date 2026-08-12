from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ModelRole = Literal["writer", "utility", "vision", "embedding", "fallback"]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Lore Studio"
    app_env: str = "development"
    database_url: str = "sqlite:///./lore_studio.db"
    app_config_root: Path = PROJECT_ROOT / "config"
    cors_origins: str = "http://localhost:5173"

    writer_model_base_url: str = "http://localhost:8080/v1"
    writer_model_api_key: str = "local"
    writer_model_name: str = ""
    writer_model_timeout_seconds: int = Field(default=600, ge=1)
    writer_context_budget: int = Field(default=60_000, ge=1_024)
    writer_disable_thinking: bool = False

    utility_model_base_url: str = "http://localhost:8080/v1"
    utility_model_api_key: str = "local"
    utility_model_name: str = ""
    utility_model_timeout_seconds: int = Field(default=240, ge=1)
    utility_context_budget: int = Field(default=24_000, ge=1_024)
    utility_disable_thinking: bool = False

    vision_model_base_url: str = "http://localhost:8080/v1"
    vision_model_api_key: str = "local"
    vision_model_name: str = ""
    vision_model_timeout_seconds: int = Field(default=300, ge=1)
    vision_context_budget: int = Field(default=24_000, ge=1_024)
    vision_disable_thinking: bool = False

    qwen_selectable_model_base_url: str = "http://host.docker.internal:18091/v1"
    qwen_selectable_model_api_key: str = "EMPTY"
    qwen_selectable_model_name: str = "qwen36-heretic-mtp"
    qwen_selectable_model_timeout_seconds: int = Field(default=600, ge=1)
    qwen_selectable_context_budget: int = Field(default=24_000, ge=1_024)
    qwen_selectable_disable_thinking: bool = True

    gemma_selectable_model_base_url: str = "http://host.docker.internal:18093/v1"
    gemma_selectable_model_api_key: str = "EMPTY"
    gemma_selectable_model_name: str = "gemma4-26b-heretic-mtp"
    gemma_selectable_model_timeout_seconds: int = Field(default=600, ge=1)
    gemma_selectable_context_budget: int = Field(default=24_000, ge=1_024)
    gemma_selectable_disable_thinking: bool = True

    fallback_model_base_url: str = ""
    fallback_model_api_key: str = "local"
    fallback_model_name: str = ""
    fallback_model_timeout_seconds: int = Field(default=300, ge=1)
    allow_utility_writer_fallback: bool = True

    embedding_enabled: bool = True
    embedding_provider: str = "openai_compatible"
    embedding_base_url: str = "http://localhost:8081/v1"
    embedding_api_key: str = "local"
    embedding_model: str = "bge-m3"
    embedding_dimension: int = Field(default=1024, ge=1)
    embedding_version: str = "bge-m3-v1"
    embedding_batch_size: int = Field(default=16, ge=1, le=256)
    embedding_timeout_seconds: int = Field(default=180, ge=1)

    model_retry_attempts: int = Field(default=2, ge=0, le=5)
    allow_model_download: bool = False
    lore_studio_model_dir: Path = Path("/models/lore-studio")
    fallback_model_hf_repo: str = ""
    fallback_model_hf_file: str = ""
    fallback_mmproj_hf_file: str = ""

    run_local_model_tests: bool = False
    run_embedding_tests: bool = False
    run_vision_tests: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def model_profile(self, role: ModelRole) -> dict[str, object]:
        prefix = role
        if role == "embedding":
            return {
                "role": role,
                "base_url": self.embedding_base_url,
                "api_key": self.embedding_api_key,
                "model": self.embedding_model,
                "timeout_seconds": self.embedding_timeout_seconds,
                "context_budget": 8_192,
            }
        base_url = str(getattr(self, f"{prefix}_model_base_url"))
        api_key = str(getattr(self, f"{prefix}_model_api_key"))
        model = str(getattr(self, f"{prefix}_model_name"))
        timeout = int(getattr(self, f"{prefix}_model_timeout_seconds"))
        context_budget = int(getattr(self, f"{prefix}_context_budget", 24_000))
        disable_thinking = bool(getattr(self, f"{prefix}_disable_thinking", False))
        return {
            "role": role,
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "timeout_seconds": timeout,
            "context_budget": context_budget,
            "disable_thinking": disable_thinking,
        }


settings = Settings()
