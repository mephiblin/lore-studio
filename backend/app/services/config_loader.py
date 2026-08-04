from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import WritingRecipe


def _load_yaml_files(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        data["_source_file"] = str(path)
        items.append(data)
    return items


def load_page_templates() -> list[dict[str, Any]]:
    return _load_yaml_files(settings.app_config_root / "page_templates")


def load_output_profiles() -> list[dict[str, Any]]:
    return _load_yaml_files(settings.app_config_root / "output_profiles")


def load_direction_card_presets() -> list[dict[str, Any]]:
    return _load_yaml_files(settings.app_config_root / "direction_card_presets")


def load_prompt(name: str) -> str:
    path = settings.app_config_root / "prompts" / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def seed_builtin_recipes(db: Session) -> None:
    for data in _load_yaml_files(settings.app_config_root / "writing_recipes"):
        key = str(data.get("key", "")).strip()
        version = str(data.get("version", "1.0.0")).strip()
        if not key:
            continue
        existing = db.scalar(
            select(WritingRecipe).where(
                WritingRecipe.key == key,
                WritingRecipe.version == version,
            )
        )
        clean = {k: v for k, v in data.items() if not k.startswith("_")}
        if existing:
            existing.name = str(data.get("name", key))
            existing.description = str(data.get("description", ""))
            existing.recipe_json = clean
            existing.is_builtin = True
        else:
            db.add(
                WritingRecipe(
                    key=key,
                    version=version,
                    name=str(data.get("name", key)),
                    description=str(data.get("description", "")),
                    recipe_json=clean,
                    is_builtin=True,
                )
            )
    db.commit()
