import pytest

from app.services.writing_moves import canonicalize_recipe_json


def test_recipe_sequence_derives_labels_and_purposes_from_moves() -> None:
    normalized = canonicalize_recipe_json(
        {
            "required_moves": ["ORIENT", "ANCHOR", "INTERPRET"],
            "pattern_preview": ["임의 표시 1", "임의 표시 2", "임의 표시 3"],
            "moves": [
                {"id": "ORIENT", "purpose": "사용자가 임의로 바꾼 목적"},
            ],
        }
    )

    assert normalized["pattern_preview"] == ["배경 설명", "핵심 사실 제시", "의미 해설"]
    assert normalized["moves"][0] == {
        "id": "ORIENT",
        "purpose": "독자가 상황을 이해하도록 장소·시대·배경부터 설명합니다.",
    }


def test_recipe_sequence_rejects_unknown_move() -> None:
    with pytest.raises(ValueError, match="지원하지 않는 문단 방식"):
        canonicalize_recipe_json(
            {"required_moves": ["ORIENT", "UNKNOWN", "INTERPRET"]}
        )
