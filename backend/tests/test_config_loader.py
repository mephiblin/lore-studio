from pathlib import Path

from conftest import isolated_session
from sqlalchemy import select

from app.models import VoiceProfile
from app.services import config_loader
from app.services.writing_moves import canonicalize_recipe_json


def test_yaml_loader_reads_recipe_directory(tmp_path: Path, monkeypatch) -> None:
    recipe_dir = tmp_path / "writing_recipes"
    recipe_dir.mkdir()
    (recipe_dir / "sample.yaml").write_text(
        "key: sample\nversion: '1.0.0'\nname: Sample\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_loader.settings, "app_config_root", tmp_path)
    items = config_loader._load_yaml_files(recipe_dir)
    assert items[0]["key"] == "sample"


def test_builtin_recipes_are_shared_progression_patterns() -> None:
    config_root = Path(__file__).resolve().parents[2] / "config"
    recipes = config_loader._load_yaml_files(config_root / "writing_recipes")
    assert len(recipes) >= 5
    assert len({recipe["key"] for recipe in recipes}) == len(recipes)
    for recipe in recipes:
        assert recipe["best_for"]
        assert recipe["required_moves"]
        assert "pattern_preview" not in recipe
        assert "moves" not in recipe
        canonical = canonicalize_recipe_json(recipe)
        assert len(canonical["pattern_preview"]) == len(recipe["required_moves"])
        assert [move["id"] for move in canonical["moves"][: len(recipe["required_moves"])]] == recipe[
            "required_moves"
        ]

    assert {"reflective_essay", "analytical_report", "field_lore_warning"}.issubset(
        {recipe["key"] for recipe in recipes}
    )

    field_recipe = next(recipe for recipe in recipes if recipe["key"] == "field_lore_warning")
    assert field_recipe["required_moves"] == [
        "ORIENT",
        "ANCHOR",
        "EXEMPLIFY",
        "WITHHOLD",
        "ESCALATE",
        "STING",
    ]
    assert "max_tokens" not in field_recipe
    assert "length_presets" not in field_recipe


def test_in_universe_oral_profile_uses_existing_generation_length_contract() -> None:
    config_root = Path(__file__).resolve().parents[2] / "config"
    profiles = config_loader._load_yaml_files(config_root / "output_profiles")
    profile = next(item for item in profiles if item["key"] == "in_universe_oral")

    assert profile["rules"]["narrator_scope"] == "in_universe_bounded"
    assert profile["rules"]["finished_manuscript_only"] is True
    assert "target_units" not in profile["rules"]
    assert "length_presets" not in profile
    assert "max_tokens" not in profile


def test_output_and_sampling_profiles_are_separate_complete_contracts() -> None:
    config_root = Path(__file__).resolve().parents[2] / "config"
    outputs = config_loader._load_yaml_files(config_root / "output_profiles")
    sampling = config_loader._load_yaml_files(config_root / "sampling_profiles")
    sampling_keys = {item["key"] for item in sampling}

    assert {"source_curation", "lore_article", "novel_prose"}.issubset(
        {item["key"] for item in outputs}
    )
    symbolic = next(item for item in outputs if item["key"] == "symbolic_tale")
    assert symbolic["recommended_recipe_keys"] == ["spatial_procession"]
    assert symbolic["recommended_voice_profile_key"] == "ceremonial_gothic"
    assert symbolic["rules"]["recurring_signal_invariant"] is True
    assert symbolic["rules"]["symbolic_explanation"] == "forbidden"
    assert symbolic["rules"]["ending_explanatory_coda"] is False
    assert sampling_keys == {"precise", "balanced", "expressive"}
    for profile in outputs:
        assert profile["recommended_sampling_profile"] in sampling_keys
        assert profile["recommended_recipe_keys"]
        assert profile["recommended_voice_profile_key"]
        assert "length_presets" not in profile
        assert "target_units" not in profile["rules"]
        assert "max_tokens" not in profile
    for profile in sampling:
        assert set(profile["parameters"]) == {
            "temperature",
            "top_p",
            "top_k",
            "frequency_penalty",
            "presence_penalty",
        }
        assert "max_tokens" not in profile["parameters"]


def test_builtin_voice_profiles_are_shared_approved_and_idempotent() -> None:
    db = isolated_session()
    config_loader.seed_builtin_voice_profiles(db)
    config_loader.seed_builtin_voice_profiles(db)

    profiles = list(db.scalars(select(VoiceProfile).order_by(VoiceProfile.key)).all())
    assert {profile.key for profile in profiles} >= {
        "fiction_scene",
        "reflective_essay",
        "analytical_report",
        "field_witness",
        "ceremonial_gothic",
    }
    assert all(profile.project_id is None for profile in profiles)
    assert all(profile.status == "APPROVED" and profile.is_builtin for profile in profiles)
    assert len(profiles) == len({(profile.key, profile.version) for profile in profiles})
