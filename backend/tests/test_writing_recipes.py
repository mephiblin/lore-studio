import pytest

from app.services.harness import _normalize_plan
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

    assert normalized["pattern_preview"] == ["맥락 열기", "핵심 근거·장면", "의미·분석"]
    assert normalized["moves"][0] == {
        "id": "ORIENT",
        "purpose": "독자가 글의 질문과 상황을 이해하도록 필요한 맥락을 엽니다.",
    }


def test_recipe_sequence_rejects_unknown_move() -> None:
    with pytest.raises(ValueError, match="지원하지 않는 문단 방식"):
        canonicalize_recipe_json(
            {"required_moves": ["ORIENT", "UNKNOWN", "INTERPRET"]}
        )


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ({"length": "short"}, 1200),
        ({"length": "long"}, 6500),
        ({"length": "custom", "custom_length": 5555}, 5555),
    ],
)
def test_plan_budgets_are_scaled_to_selected_length(settings: dict, expected: int) -> None:
    plan = _normalize_plan(
        {
            "title": "분량 검증",
            "angle": "선택한 길이를 지킨다.",
            "blocks": [
                {"move": "ORIENT", "purpose": "맥락", "word_budget": 100},
                {"move": "ANCHOR", "purpose": "근거", "word_budget": 200},
                {"move": "INTERPRET", "purpose": "결론", "word_budget": 100},
            ],
        },
        {
            "generation_settings": settings,
            "selected_concepts": [],
            "writing_recipe": {
                "required_moves": ["ORIENT", "ANCHOR", "INTERPRET"],
                "optional_moves": [],
            },
        },
    )

    assert plan["target_length"] == expected
    assert plan["planned_length"] == expected
    assert sum(block["word_budget"] for block in plan["blocks"]) == expected
    assert plan["blocks"][1]["word_budget"] > plan["blocks"][0]["word_budget"]


def test_plan_replaces_hallucinated_evidence_id_with_selected_source() -> None:
    selected_id = "becd8141-a8f2-458e-a44b-5889f0145406"
    plan = _normalize_plan(
        {
            "title": "근거 경계",
            "angle": "선택 자료만 사용한다.",
            "blocks": [
                {
                    "move": "ANCHOR",
                    "purpose": "선택 근거를 고정한다.",
                    "evidence_ids": ["becd8141-a8f2-4589f0145406"],
                    "word_budget": 1200,
                    "must_include": ["확정 사실"],
                    "avoid": [],
                }
            ],
        },
        {
            "generation_settings": {"length": "short"},
            "selected_concepts": [{"id": selected_id, "title": "확정 자료"}],
            "writing_recipe": {},
        },
    )

    assert plan["blocks"][0]["evidence_ids"] == [selected_id]
    assert any("근거 ID" in warning for warning in plan["warnings"])
