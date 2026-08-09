from __future__ import annotations

from typing import Any

MOVE_LABELS = {
    "ORIENT": "맥락 열기",
    "NARROW": "초점 좁히기",
    "ANCHOR": "핵심 근거·장면",
    "COMPLICATE": "문제·예외 검토",
    "COMPARE": "비교·대조",
    "EXEMPLIFY": "사례·장면",
    "ESCALATE": "긴장·중요도 높이기",
    "INTERPRET": "의미·분석",
    "WITHHOLD": "답을 유보하기",
    "TURN": "관점 전환",
    "STING": "결론·여운",
}

MOVE_DESCRIPTIONS = {
    "ORIENT": "독자가 글의 질문과 상황을 이해하도록 필요한 맥락을 엽니다.",
    "NARROW": "넓은 주제에서 이번 글이 다룰 대상이나 쟁점으로 초점을 좁힙니다.",
    "ANCHOR": "글의 중심이 되는 근거, 관찰, 장면 또는 주장을 구체적으로 제시합니다.",
    "COMPLICATE": "첫 설명만으로 풀리지 않는 문제, 예외, 반론 또는 대가를 검토합니다.",
    "COMPARE": "대상, 관점, 전후 상황을 비교해 차이와 기준을 드러냅니다.",
    "EXEMPLIFY": "추상적인 생각이나 규칙을 구체적인 사례 또는 장면으로 보여 줍니다.",
    "ESCALATE": "갈등, 중요도, 영향 범위를 높여 다음 판단이나 선택으로 이끕니다.",
    "INTERPRET": "앞서 제시한 근거나 경험이 무엇을 뜻하는지 분석하고 해석합니다.",
    "WITHHOLD": "근거가 부족한 답을 단정하지 않고 질문이나 판단을 유보합니다.",
    "TURN": "새 근거, 반론, 깨달음을 제시해 글의 관점이나 방향을 전환합니다.",
    "STING": "핵심 결론, 이미지 또는 질문으로 글의 의미와 여운을 남깁니다.",
}


def canonicalize_recipe_json(value: dict[str, Any]) -> dict[str, Any]:
    recipe = dict(value)
    raw_required = recipe.get("required_moves")
    if not isinstance(raw_required, list):
        raise ValueError("전개 방식에는 세 단계 이상의 필수 문단 방식이 필요합니다.")
    required = [str(move).strip().upper() for move in raw_required if str(move).strip()]
    if len(required) < 3:
        raise ValueError("전개 방식에는 세 단계 이상의 필수 문단 방식이 필요합니다.")
    unknown = [move for move in required if move not in MOVE_LABELS]
    if unknown:
        raise ValueError(f"지원하지 않는 문단 방식입니다: {', '.join(dict.fromkeys(unknown))}")

    raw_optional = recipe.get("optional_moves", [])
    optional = (
        [str(move).strip().upper() for move in raw_optional if str(move).strip()]
        if isinstance(raw_optional, list)
        else []
    )
    optional = [move for move in optional if move in MOVE_LABELS and move not in required]
    defined = list(dict.fromkeys([*required, *optional]))

    recipe["required_moves"] = required
    recipe["optional_moves"] = optional
    recipe["pattern_preview"] = [MOVE_LABELS[move] for move in required]
    recipe["moves"] = [{"id": move, "purpose": MOVE_DESCRIPTIONS[move]} for move in defined]
    recipe.setdefault("planner_rules", [])
    recipe.setdefault("audit_rules", [])
    recipe.setdefault("style_defaults", {})
    return recipe
