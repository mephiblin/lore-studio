from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import PlaybookSessionCreate
from app.services import config_loader
from app.services.sampling import resolve_sampling_profile, writer_call_settings


def test_sampling_profile_resolves_overrides_without_owning_length() -> None:
    profile = resolve_sampling_profile(
        {
            "length": "long",
            "sampling_profile": "expressive",
            "sampling_overrides": {"temperature": 0.81, "top_k": 55},
        }
    )
    assert profile["key"] == "expressive"
    assert profile["parameters"]["temperature"] == 0.81
    assert profile["parameters"]["top_k"] == 55
    assert set(profile["overridden_parameters"]) == {"temperature", "top_k"}
    assert "length" not in profile["parameters"]
    assert "max_tokens" not in profile["parameters"]


def test_finalizer_derives_a_conservative_pass_from_selected_sampling() -> None:
    profile = resolve_sampling_profile({"sampling_profile": "expressive"})
    temperature, params = writer_call_settings(profile)
    final_temperature, final_params = writer_call_settings(profile, finalizer=True)
    assert temperature == 0.72
    assert params["top_k"] == 44
    assert final_temperature == 0.48
    assert final_params["top_p"] == 0.86
    assert final_params["top_k"] == 32


def test_sampling_override_ranges_are_validated_at_api_schema_boundary() -> None:
    with pytest.raises(ValidationError):
        PlaybookSessionCreate(
            project_id="project",
            writing_recipe_id="recipe",
            settings_json={
                "sampling_profile": "balanced",
                "sampling_overrides": {"top_p": 1.2},
            },
        )


def test_sampling_profile_files_are_available_from_backend_workdir() -> None:
    assert Path(config_loader.settings.app_config_root / "sampling_profiles").exists()
    assert len(config_loader.load_sampling_profiles()) == 3
