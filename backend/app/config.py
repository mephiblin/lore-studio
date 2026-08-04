from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lore Studio"
    app_env: str = "development"
    database_url: str = "sqlite:///./lore_studio.db"
    app_config_root: Path = Path("../config")
    cors_origins: str = "http://localhost:5173"

    mock_model: bool = True
    model_base_url: str = "http://localhost:8001/v1"
    model_api_key: str = "local"
    model_name: str = "local-writer"
    model_timeout_seconds: int = Field(default=300, ge=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
