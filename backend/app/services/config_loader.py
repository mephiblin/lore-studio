from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CategoryDefinition, Project, VoiceProfile, WritingRecipe
from app.schemas import canonicalize_voice_profile_json
from app.services.writing_moves import canonicalize_recipe_json


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


def seed_project_categories(db: Session, project: Project) -> list[CategoryDefinition]:
    """Copy starter categories into a project; afterward they are project-owned and editable."""
    existing_keys = set(
        db.scalars(
            select(CategoryDefinition.key).where(CategoryDefinition.project_id == project.id)
        ).all()
    )
    created: list[CategoryDefinition] = []
    for data in load_page_templates():
        key = str(data.get("key", "")).strip()
        if not key or key in existing_keys:
            continue
        template = {k: v for k, v in data.items() if not k.startswith("_")}
        category = CategoryDefinition(
            project_id=project.id,
            key=key,
            name=str(data.get("name", key)),
            description="",
            template_json=template,
            is_builtin=False,
        )
        db.add(category)
        created.append(category)
        existing_keys.add(key)
    return created


def load_output_profiles() -> list[dict[str, Any]]:
    return _load_yaml_files(settings.app_config_root / "output_profiles")


def load_sampling_profiles() -> list[dict[str, Any]]:
    return _load_yaml_files(settings.app_config_root / "sampling_profiles")


def load_direction_card_presets() -> list[dict[str, Any]]:
    return _load_yaml_files(settings.app_config_root / "direction_card_presets")


def load_voice_profiles() -> list[dict[str, Any]]:
    return _load_yaml_files(settings.app_config_root / "voice_profiles")


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
                WritingRecipe.project_id.is_(None),
            )
        )
        clean = canonicalize_recipe_json({k: v for k, v in data.items() if not k.startswith("_")})
        if existing:
            existing.name = str(data.get("name", key))
            existing.description = str(data.get("description", ""))
            existing.recipe_json = clean
            existing.is_builtin = True
            existing.approved = True
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
    db.flush()
    for recipe in db.scalars(select(WritingRecipe)).all():
        try:
            normalized = canonicalize_recipe_json(recipe.recipe_json or {})
        except ValueError:
            continue
        if normalized != recipe.recipe_json:
            recipe.recipe_json = normalized
    db.commit()


def seed_builtin_voice_profiles(db: Session) -> None:
    """Upsert shared, example-free expression contracts shipped with the app."""
    for data in load_voice_profiles():
        key = str(data.get("key", "")).strip()
        version = str(data.get("version", "1.0.0")).strip()
        if not key:
            continue
        profile_json = canonicalize_voice_profile_json(data.get("profile_json") or {})
        existing = db.scalar(
            select(VoiceProfile).where(
                VoiceProfile.key == key,
                VoiceProfile.version == version,
                VoiceProfile.project_id.is_(None),
            )
        )
        if existing:
            existing.name = str(data.get("name", key))
            existing.description = str(data.get("description", ""))
            existing.profile_json = profile_json
            existing.is_builtin = True
            existing.status = "APPROVED"
        else:
            db.add(
                VoiceProfile(
                    project_id=None,
                    key=key,
                    version=version,
                    name=str(data.get("name", key)),
                    description=str(data.get("description", "")),
                    profile_json=profile_json,
                    is_builtin=True,
                    status="APPROVED",
                )
            )
    db.commit()
