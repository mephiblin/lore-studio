from __future__ import annotations

from typing import Any

MOVE_LABELS = {
    "ORIENT": "배경 설명",
    "NARROW": "주제로 초점 이동",
    "ANCHOR": "핵심 사실 제시",
    "COMPLICATE": "문제·예외 추가",
    "COMPARE": "차이 비교",
    "EXEMPLIFY": "사례 제시",
    "ESCALATE": "긴장 고조",
    "INTERPRET": "의미 해설",
    "WITHHOLD": "의문 남기기",
    "TURN": "관점 전환",
    "STING": "마지막 여운",
}

MOVE_DESCRIPTIONS = {
    "ORIENT": "독자가 상황을 이해하도록 장소·시대·배경부터 설명합니다.",
    "NARROW": "넓은 배경에서 이 글의 핵심 인물이나 사건으로 초점을 옮깁니다.",
    "ANCHOR": "이 글에서 반드시 기억해야 할 설정이나 사실을 분명히 제시합니다.",
    "COMPLICATE": "단순한 설명으로 끝나지 않도록 문제, 예외, 대가를 덧붙입니다.",
    "COMPARE": "두 대상이나 전후 상황의 차이를 비교해 특징을 드러냅니다.",
    "EXEMPLIFY": "추상적인 설정을 실제 사건이나 구체적인 사례로 보여 줍니다.",
    "ESCALATE": "위험이나 갈등을 키워 다음 내용을 궁금하게 만듭니다.",
    "INTERPRET": "앞서 제시한 사실이 세계나 인물에게 어떤 의미인지 풀이합니다.",
    "WITHHOLD": "아직 정하지 않은 답을 단정하지 않고 의문으로 남깁니다.",
    "TURN": "새 정보나 다른 관점을 제시해 글의 방향을 바꿉니다.",
    "STING": "핵심 이미지나 질문을 남겨 글을 짧고 선명하게 마무리합니다.",
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
