from pathlib import Path

from app.services import config_loader


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
