from pathlib import Path

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
