from __future__ import annotations

from typing import Any

from app.services.config_loader import load_sampling_profiles

SAMPLING_PARAMETER_KEYS = (
    "temperature",
    "top_p",
    "top_k",
    "frequency_penalty",
    "presence_penalty",
)


def resolve_sampling_profile(
    generation_settings: dict[str, Any] | None,
    *,
    recommended_key: str | None = None,
) -> dict[str, Any]:
    settings = generation_settings or {}
    profiles = {
        str(item.get("key")): item
        for item in load_sampling_profiles()
        if str(item.get("key", "")).strip()
    }
    key = str(settings.get("sampling_profile") or recommended_key or "balanced")
    profile = profiles.get(key)
    if profile is None:
        raise ValueError("선택한 생성 성향을 찾을 수 없습니다.")
    parameters = {
        name: profile.get("parameters", {}).get(name)
        for name in SAMPLING_PARAMETER_KEYS
    }
    overrides = settings.get("sampling_overrides") or {}
    for name in SAMPLING_PARAMETER_KEYS:
        if overrides.get(name) is not None:
            parameters[name] = overrides[name]
    return {
        "key": key,
        "version": str(profile.get("version", "1.0.0")),
        "name": str(profile.get("name", key)),
        "description": str(profile.get("description", "")),
        "parameters": parameters,
        "overridden_parameters": [
            name for name in SAMPLING_PARAMETER_KEYS if overrides.get(name) is not None
        ],
    }


def writer_call_settings(profile: dict[str, Any], *, finalizer: bool = False) -> tuple[float, dict[str, Any]]:
    parameters = dict(profile.get("parameters") or {})
    temperature = float(parameters.pop("temperature", 0.58))
    if finalizer:
        temperature = min(temperature, 0.48)
        parameters["top_p"] = min(float(parameters.get("top_p", 0.86)), 0.86)
        parameters["top_k"] = min(int(parameters.get("top_k", 32)), 32)
    return temperature, {key: value for key, value in parameters.items() if value is not None}
