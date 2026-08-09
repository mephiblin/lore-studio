from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    GenerationRun,
    GenerationStage,
    LoreBlock,
    LoreDocument,
    LoreRevision,
    PlaybookSession,
    WritingRecipe,
)
from app.services.audits import run_audits
from app.services.config_loader import load_output_profiles, load_prompt
from app.services.context_compiler import UNSET, compile_context
from app.services.model_gateway import ModelCallResult, ModelGateway
from app.services.revisions import add_lore_revision

LENGTH_BUDGETS = {
    "short": 1200,
    "normal": 3000,
    "long": 6500,
    "very_long": 12000,
}

LONG_FORM_THRESHOLD = 6000
LONG_FORM_MINIMUM_RATIO = 0.95
LONG_FORM_MAXIMUM_RATIO = 1.1
LONG_FORM_MAX_CALLS_PER_BLOCK = 14
LONG_FORM_SEGMENT_FOCI = (
    "아직 쓰지 않은 직접 관찰과 자료 근거를 구체화한다.",
    "관찰된 사실과 그로부터 가능한 해석을 명시적으로 구분한다.",
    "이미 제시한 결과의 작동 과정과 인과 사슬을 한 단계 더 풀어낸다.",
    "공간적 위치·범위·경계가 의미에 미치는 영향을 분석한다.",
    "시간의 전후 관계와 변화 또는 정체가 뜻하는 바를 검토한다.",
    "명칭·개념·분류가 설명하는 것과 설명하지 못하는 것을 가른다.",
    "첫 해석과 다른 대안적 독해를 제시하되 어느 쪽도 사실로 확정하지 않는다.",
    "현재 해석에 대한 반론·예외·한계를 검토한다.",
    "자료가 답하지 않는 질문과 추가로 필요한 근거를 구체적으로 밝힌다.",
    "앞선 세부가 더 큰 장소·제도·역사적 맥락에서 갖는 의미를 연결한다.",
    "같은 사실을 반복 설명하지 말고 독자가 체감할 구체적 결과를 보여 준다.",
    "주장의 적용 범위와 일반화할 수 없는 경계를 분명히 한다.",
    "서로 떨어진 두 근거의 관계를 비교해 공통점과 차이를 드러낸다.",
    "새 사실 없이 남은 분석을 수렴하고 다음 전개로 자연스럽게 이행한다.",
)
LONG_FORM_NOVEL_FOCI = (
    "인물의 현재 욕망이 드러나는 구체적인 행동을 전진시킨다.",
    "시각·소리·촉감·거리감 가운데 아직 쓰지 않은 감각으로 장면을 구체화한다.",
    "행동을 막는 장애물과 인물이 즉시 치르는 대가를 보여 준다.",
    "상대의 말과 행동 사이의 어긋남을 대화와 반응으로 드러낸다.",
    "인물의 판단이 바뀌는 짧은 계기와 그 직후의 선택을 쓴다.",
    "공간 안의 위치와 이동을 분명히 해 장면의 동선을 전진시킨다.",
    "설정을 설명하지 말고 인물이 사용하거나 피하는 방식으로 노출한다.",
    "앞선 행동의 예상 밖 결과를 발생시켜 긴장을 한 단계 높인다.",
    "겉으로 한 행동과 속으로 억누른 반응의 차이를 보여 준다.",
    "인물 관계가 가까워지거나 멀어지는 구체적인 교환을 배치한다.",
    "긴 호흡 뒤 짧은 결정이나 사건을 두어 문장 리듬을 바꾼다.",
    "아직 답하지 않을 정보는 정답 대신 관찰 가능한 흔적으로 남긴다.",
    "이전 장면의 세부를 다른 의미로 되돌려 현재 선택과 연결한다.",
    "같은 감정 설명을 반복하지 말고 다음 행동·장면으로 이행한다.",
)
LONG_FORM_ESSAY_FOCI = (
    "성찰의 출발점이 된 한 순간을 구체적인 경험으로 되살린다.",
    "그때의 감각과 몸의 반응을 아직 쓰지 않은 세부로 보여 준다.",
    "당시 믿었던 것과 지금 이해하는 것의 차이를 분명히 한다.",
    "생각이 흔들린 계기와 그 변화가 즉시 만든 선택을 연결한다.",
    "개인적 경험을 더 넓은 질문과 연결하되 성급히 일반화하지 않는다.",
    "첫 해석과 충돌하는 기억이나 예외를 정직하게 검토한다.",
    "감정의 이름을 반복하지 말고 행동·장면·이미지로 드러낸다.",
    "시간이 지난 뒤 달라진 관점과 여전히 남은 의문을 나눈다.",
    "다른 사람의 관점을 추측으로 단정하지 않고 관찰 범위를 밝힌다.",
    "경험에서 얻은 통찰이 실제 생활에 만든 작은 결과를 보여 준다.",
    "앞서 등장한 사물이나 이미지를 새 의미로 되돌려 쓴다.",
    "자신의 해석이 적용되지 않는 경계와 한계를 인정한다.",
    "서로 떨어진 두 경험을 비교해 변화의 방향을 드러낸다.",
    "교훈을 선언하지 말고 남은 질문이나 구체적 장면으로 수렴한다.",
)

REFINEMENT_PRIORITIES = {
    "coherence": "문단 사이의 시간·관점·논리 연결을 자연스럽게 만든다.",
    "causality": "사건과 주장 사이의 원인·결과 관계를 선명하게 만든다.",
    "imagery": "초안의 사실을 바꾸지 않고 장면·감각·구체성을 보강한다.",
    "rhythm": "문장 길이와 문단 호흡의 단조로움을 다듬는다.",
    "deduplicate": "겹치는 도입과 설명을 합치고 반복을 제거한다.",
    "ending": "초안의 결론을 유지하면서 마지막 문단의 수렴과 여운을 강화한다.",
}
REFINEMENT_INTENSITIES = {
    "light": "문장 표현과 접속만 손보고 문단 구조는 유지한다.",
    "balanced": "핵심 내용은 유지하면서 필요할 때 문단을 합치거나 나눈다.",
    "strong": "핵심 사실과 사용자 의도를 보존하되 완성도를 위해 문단 순서를 재배열할 수 있다.",
}
REFINEMENT_LENGTH_POLICIES = {
    "preserve": "초안 전체 분량을 대체로 유지한다.",
    "tighten": "중복과 군더더기를 줄여 초안보다 간결하게 만든다.",
    "expand": "새 사실을 만들지 않는 범위에서 연결·장면·근거 설명을 보강한다.",
}

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "angle", "blocks"],
    "properties": {
        "title": {"type": "string"},
        "angle": {"type": "string"},
        "blocks": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "move",
                    "purpose",
                    "evidence_ids",
                    "word_budget",
                    "must_include",
                    "avoid",
                    "scene_mode",
                    "expression_focus",
                ],
                "properties": {
                    "move": {"type": "string"},
                    "purpose": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "word_budget": {"type": "integer", "minimum": 50},
                    "must_include": {"type": "array", "items": {"type": "string"}},
                    "avoid": {"type": "array", "items": {"type": "string"}},
                    "scene_mode": {"type": "string"},
                    "expression_focus": {"type": "string"},
                    "locked": {"type": "boolean"},
                },
            },
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
}


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _selected_ids(session: PlaybookSession) -> list[str]:
    result: list[str] = []
    for ids in (session.concept_slots or {}).values():
        for page_id in ids or []:
            if page_id not in result:
                result.append(page_id)
    return result


def _json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("모델 출력에서 JSON 객체를 찾을 수 없습니다.")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Planner 출력은 JSON 객체여야 합니다.")
    return data


def _target_length(pack: dict[str, Any]) -> int:
    settings = pack.get("generation_settings", {})
    length = str(settings.get("length", "normal"))
    if length == "custom":
        try:
            return max(500, int(settings.get("custom_length") or 4000))
        except (TypeError, ValueError):
            return 4000
    return LENGTH_BUDGETS.get(length, 3000)


def _fit_block_budgets(raw_budgets: list[int], target: int) -> list[int]:
    """Scale planner ratios to an exact Korean-character target with a 50-char floor."""
    if not raw_budgets:
        return []
    minimum = 50
    target = max(target, minimum * len(raw_budgets))
    weights = [max(1, int(value)) for value in raw_budgets]
    weight_total = sum(weights)
    available = target - minimum * len(weights)
    exact = [available * weight / weight_total for weight in weights]
    budgets = [minimum + int(value) for value in exact]
    remainder = target - sum(budgets)
    order = sorted(range(len(weights)), key=lambda index: exact[index] % 1, reverse=True)
    for index in order[:remainder]:
        budgets[index] += 1
    return budgets


def _normalize_refinement(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = value or {}
    priorities = [
        key for key in raw.get("priorities", []) if key in REFINEMENT_PRIORITIES
    ]
    if not priorities:
        priorities = ["coherence", "deduplicate", "rhythm"]
    priorities = list(dict.fromkeys(priorities))
    intensity = str(raw.get("intensity", "balanced"))
    if intensity not in REFINEMENT_INTENSITIES:
        intensity = "balanced"
    length_policy = str(raw.get("length_policy", "preserve"))
    if length_policy not in REFINEMENT_LENGTH_POLICIES:
        length_policy = "preserve"
    return {
        "priorities": priorities,
        "priority_instructions": [REFINEMENT_PRIORITIES[key] for key in priorities],
        "intensity": intensity,
        "intensity_instruction": REFINEMENT_INTENSITIES[intensity],
        "length_policy": length_policy,
        "length_instruction": REFINEMENT_LENGTH_POLICIES[length_policy],
    }


def _normalize_plan(data: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("structure_plan", data)
    if not isinstance(raw, dict):
        raise ValueError("Planner 출력의 최상위 구조가 올바르지 않습니다.")
    raw_blocks = raw.get("blocks", [])
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise ValueError("Planner 출력에 하나 이상의 blocks가 필요합니다.")
    target = _target_length(pack)
    selected_ids = [str(item.get("id")) for item in pack.get("selected_concepts", []) if item.get("id")]
    recipe = pack.get("writing_recipe", {}) if isinstance(pack.get("writing_recipe"), dict) else {}
    required_moves = [str(move).strip().upper() for move in recipe.get("required_moves", []) if str(move).strip()]
    optional_moves = [str(move).strip().upper() for move in recipe.get("optional_moves", []) if str(move).strip()]
    move_purposes = {
        str(item.get("id", "")).strip().upper(): str(item.get("purpose", "")).strip()
        for item in recipe.get("moves", [])
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    normalized_sources: list[dict[str, Any]] = [item for item in raw_blocks if isinstance(item, dict)]
    recipe_adjusted = False
    if required_moves:
        contracted: list[dict[str, Any]] = []
        for index, move in enumerate(required_moves):
            source = dict(normalized_sources[index]) if index < len(normalized_sources) else {}
            original_move = str(source.get("move") or source.get("rhetorical_move") or "").strip().upper()
            if original_move != move:
                recipe_adjusted = True
                source["purpose"] = move_purposes.get(
                    move, "선택한 전개 단계의 목적을 수행한다."
                )
            source["move"] = move
            if not str(source.get("purpose", "")).strip():
                source["purpose"] = move_purposes.get(move, "선택한 전개 단계의 목적을 수행한다.")
            contracted.append(source)
        for source in normalized_sources[len(required_moves):]:
            move = str(source.get("move") or source.get("rhetorical_move") or "").strip().upper()
            if move in optional_moves:
                contracted.append({**source, "move": move})
            else:
                recipe_adjusted = True
        normalized_sources = contracted

    blocks: list[dict[str, Any]] = []
    for index, item in enumerate(normalized_sources, start=1):
        budget = item.get("word_budget")
        if not isinstance(budget, int):
            percentage = str(item.get("content_budget", "")).rstrip("%")
            try:
                budget = max(50, int(target * float(percentage) / 100))
            except ValueError:
                budget = max(50, target // len(normalized_sources))
        evidence_ids = item.get("evidence_ids")
        if not isinstance(evidence_ids, list):
            evidence_ids = selected_ids if item.get("facts_to_use") else []
        blocks.append(
            {
                "index": index,
                "move": str(item.get("move") or item.get("rhetorical_move") or "ANCHOR"),
                "purpose": str(item.get("purpose") or "선택한 근거를 설명한다."),
                "evidence_ids": [str(value) for value in evidence_ids],
                "word_budget": budget,
                "must_include": list(item.get("must_include") or []),
                "avoid": list(item.get("avoid") or item.get("must_avoid") or []),
                "scene_mode": str(item.get("scene_mode") or "설명"),
                "expression_focus": str(item.get("expression_focus") or ""),
                "locked": bool(item.get("locked", False)),
            }
        )
    if not blocks:
        raise ValueError("Planner 출력에서 유효한 block을 복구하지 못했습니다.")
    fitted_budgets = _fit_block_budgets([block["word_budget"] for block in blocks], target)
    for block, fitted_budget in zip(blocks, fitted_budgets, strict=True):
        block["word_budget"] = fitted_budget
    concept_role = raw.get("concept_role", {}) if isinstance(raw.get("concept_role"), dict) else {}
    title = raw.get("title") or concept_role.get("title")
    if not title:
        title = next((item.get("title") for item in pack.get("selected_concepts", [])), "새 로어")
    warnings = list(raw.get("warnings") or pack.get("warnings") or [])
    if recipe_adjusted:
        warnings.append("선택한 전개 방식의 필수 순서에 맞게 글의 흐름을 정렬했습니다.")
    return {
        "title": str(title),
        "angle": str(raw.get("angle") or pack.get("user_direction") or "선택 자료의 의미를 단계적으로 드러낸다."),
        "blocks": blocks,
        "target_length": target,
        "planned_length": sum(fitted_budgets),
        "warnings": warnings,
        "planner_metadata": {
            key: raw[key]
            for key in ("concept_role", "conflict_resolution", "constraints_check")
            if key in raw
        },
    }


def _record_stage(
    db: Session,
    session: PlaybookSession,
    step: str,
    *,
    input_json: dict[str, Any],
    output_json: dict[str, Any],
    run_id: str | None = None,
) -> GenerationStage:
    current = db.scalar(
        select(func.max(GenerationStage.attempt)).where(
            GenerationStage.session_id == session.id,
            GenerationStage.step == step,
        )
    )
    stage = GenerationStage(
        session_id=session.id,
        generation_run_id=run_id,
        step=step,
        attempt=int(current or 0) + 1,
        status="COMPLETED",
        input_json=input_json,
        output_json=output_json,
    )
    db.add(stage)
    return stage


def _markdown_blocks(body: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip() and not part.startswith("# ")]


def _block_json(text: str, attrs: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "loreBlock",
        "attrs": attrs,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def _plain_document_json(body: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": paragraph}]}
            for paragraph in _markdown_blocks(body)
        ],
    }


def _clean_generated_text(value: str) -> str:
    body = value.strip()
    if body.startswith("```") and body.endswith("```"):
        body = re.sub(
            r"^```(?:markdown)?\s*|\s*```$", "", body, flags=re.IGNORECASE
        ).strip()
    body = re.sub(r"^#\s+[^\n]+\n+", "", body, count=1).strip()
    return body


def _remove_continuation_overlap(previous: str, continuation: str) -> str:
    """Remove a repeated boundary when a model echoes the supplied tail."""
    if not previous or not continuation:
        return continuation
    maximum = min(600, len(previous), len(continuation))
    for size in range(maximum, 39, -1):
        if previous[-size:].strip() == continuation[:size].strip():
            return continuation[size:].lstrip()
    return continuation


def _similarity_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value).lower()


def _paragraph_is_repeated(candidate: str, existing: list[str]) -> bool:
    normalized = _similarity_text(candidate)
    if len(normalized) < 50:
        return False
    for paragraph in existing:
        other = _similarity_text(paragraph)
        if len(other) < 50:
            continue
        shorter, longer = sorted((normalized, other), key=len)
        if len(shorter) >= len(longer) * 0.72 and shorter in longer:
            return True
        if SequenceMatcher(None, normalized, other).ratio() >= 0.78:
            return True
    return False


def _unique_generated_text(candidate: str, existing_text: str) -> str:
    existing = _markdown_blocks(existing_text)
    accepted: list[str] = []
    for paragraph in _markdown_blocks(candidate):
        if not _paragraph_is_repeated(paragraph, [*existing, *accepted]):
            accepted.append(paragraph)
    return "\n\n".join(accepted).strip()


def _near_duplicate_count(body: str) -> int:
    paragraphs = _markdown_blocks(body)
    duplicates = 0
    accepted: list[str] = []
    for paragraph in paragraphs:
        if _paragraph_is_repeated(paragraph, accepted):
            duplicates += 1
        else:
            accepted.append(paragraph)
    return duplicates


def _long_form_foci(source_payload: dict[str, Any]) -> tuple[str, ...]:
    context_pack = source_payload.get("context_pack", {})
    original_request = source_payload.get("original_writing_request", {})
    output_profile = context_pack.get("output_profile") or original_request.get(
        "output_profile", {}
    )
    key = str(output_profile.get("key", "")) if isinstance(output_profile, dict) else ""
    if key == "novel_prose":
        return LONG_FORM_NOVEL_FOCI
    if key == "personal_essay":
        return LONG_FORM_ESSAY_FOCI
    return LONG_FORM_SEGMENT_FOCI


def _trim_near_sentence(text: str, target: int) -> str:
    ceiling = max(target, math.ceil(target * LONG_FORM_MAXIMUM_RATIO))
    if len(text) <= ceiling:
        return text.strip()
    floor = math.floor(target * LONG_FORM_MINIMUM_RATIO)
    endings = [
        match.end()
        for match in re.finditer(r"[.!?。](?:[\"'’”」』])?(?=\s|$)", text)
        if floor <= match.end() <= ceiling
    ]
    return text[: endings[-1]].strip() if endings else text.strip()


def _merged_usage(results: list[ModelCallResult]) -> dict[str, Any]:
    usage: dict[str, Any] = {}
    for result in results:
        for key, value in (result.usage or {}).items():
            if isinstance(value, (int, float)):
                usage[key] = usage.get(key, 0) + value
            elif key not in usage:
                usage[key] = value
    return usage


def _aggregate_calls(
    results: list[ModelCallResult],
    body: str,
    *,
    target: int,
    block_counts: list[int],
) -> ModelCallResult:
    if not results:
        raise ValueError("장문 생성 호출 결과가 없습니다.")
    return ModelCallResult(
        content=body,
        role=results[-1].role,
        model=results[-1].model,
        endpoint=results[-1].endpoint,
        params={
            "strategy": "block_segments",
            "call_count": len(results),
            "target_characters": target,
            "minimum_characters": math.floor(target * LONG_FORM_MINIMUM_RATIO),
            "actual_characters": len(body),
            "block_character_counts": block_counts,
            "calls": [result.audit_metadata() for result in results],
        },
        usage=_merged_usage(results),
        timings={"call_count": len(results)},
        fallback_from=next(
            (result.fallback_from for result in results if result.fallback_from), None
        ),
    )


class LoreHarness:
    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self.gateway = gateway or ModelGateway()

    async def _complete_long_form(
        self,
        *,
        system_prompt: str,
        source_payload: dict[str, Any],
        plan: dict[str, Any],
        target: int,
        temperature: float,
        seed: int | None,
        mode: str,
    ) -> tuple[ModelCallResult, list[int]]:
        raw_blocks = [
            dict(block) for block in plan.get("blocks", []) if isinstance(block, dict)
        ]
        if not raw_blocks:
            raw_blocks = [
                {
                    "move": "DRAFT",
                    "purpose": "선택한 자료와 지시에 맞는 완성된 글을 쓴다.",
                    "word_budget": target,
                    "must_include": [],
                    "avoid": [],
                }
            ]
        raw_budgets = [int(block.get("word_budget") or 1) for block in raw_blocks]
        if len(raw_budgets) >= 4:
            # Local writers commonly close conclusions early. Keep the ending concise and
            # spend the recovered length on evidence/analysis instead of repeated codas.
            raw_budgets[-1] = min(raw_budgets[-1], max(400, math.floor(target * 0.05)))
        budgets = _fit_block_budgets(raw_budgets, target)
        completed_sections: list[str] = []
        paragraph_plan_indexes: list[int] = []
        results: list[ModelCallResult] = []
        block_counts: list[int] = []
        segment_foci = _long_form_foci(source_payload)
        segment_prompt = (
            f"{system_prompt}\n\n"
            "# 장문 구간 작성 모드\n"
            "- 지금은 전체 글을 한 번에 끝내지 말고 active_block의 새 본문 구간만 쓴다.\n"
            "- current_block_text는 이미 작성된 부분이다. 이를 반복하거나 처음부터 다시 쓰지 말고 "
            "그 직후에 붙을 새 문장만 출력한다.\n"
            "- previous_block_tail과 자연스럽게 이어지되 같은 설명·비유·결론을 반복하지 않는다.\n"
            "- covered_paragraph_openings와 같은 주장·문단을 단어만 바꾸어 다시 쓰지 않는다. "
            "현재 focus와 맞는 새로운 분석 단위를 선택한다.\n"
            "- 내부 블록명, 목표 글자 수, 작업 설명, JSON, 제목을 출력하지 않는다.\n"
            "- requested_new_characters에 가까운 충분한 분량을 쓴다. 문장을 중간에 끊지 않는다."
        )

        for block_index, (block, block_target) in enumerate(
            zip(raw_blocks, budgets, strict=True)
        ):
            segments: list[str] = []
            minimum = math.floor(block_target * LONG_FORM_MINIMUM_RATIO)
            for attempt in range(LONG_FORM_MAX_CALLS_PER_BLOCK):
                current = "\n\n".join(segments).strip()
                if len(current) >= minimum:
                    break
                remaining = max(1, block_target - len(current))
                requested = min(3000, max(900, remaining + 600))
                segment_focus = segment_foci[attempt % len(segment_foci)]
                active_payload = {
                    "long_form_contract": {
                        "mode": mode,
                        "block_number": block_index + 1,
                        "block_count": len(raw_blocks),
                        "block_target_characters": block_target,
                        "block_minimum_characters": minimum,
                        "current_character_count": len(current),
                        "remaining_characters": remaining,
                        "requested_new_characters": requested,
                        "segment_focus": segment_focus,
                        "covered_paragraph_openings": [
                            paragraph[:120]
                            for paragraph in _markdown_blocks(
                                "\n\n".join([*completed_sections, current])
                            )[-30:]
                        ],
                        "active_block": {**block, "word_budget": block_target},
                        "next_block_purpose": (
                            raw_blocks[block_index + 1].get("purpose", "")
                            if block_index + 1 < len(raw_blocks)
                            else "글 전체를 수렴하고 마무리한다."
                        ),
                    },
                    "previous_block_tail": (
                        completed_sections[-1][-1400:] if completed_sections else ""
                    ),
                    "current_block_text": current,
                    "source_material": source_payload,
                    "instruction": (
                        "이미 쓴 부분과 겹치지 않는 새 한국어 본문만 출력하라. "
                        f"이번 응답은 반드시 다음 초점만 새롭게 전개한다: {segment_focus}"
                    ),
                }
                result = await self.gateway.complete(
                    [
                        {"role": "system", "content": segment_prompt},
                        {
                            "role": "user",
                            "content": json.dumps(active_payload, ensure_ascii=False, indent=2),
                        },
                    ],
                    role="writer",
                    temperature=temperature,
                    max_tokens=3500,
                    seed=(seed + len(results) + 1) if seed is not None else None,
                )
                results.append(result)
                segment = _unique_generated_text(
                    _remove_continuation_overlap(
                        current, _clean_generated_text(result.content)
                    ),
                    "\n\n".join([*completed_sections, current]),
                )
                if len(segment) < 40 or segment in current:
                    continue
                segments.append(segment)

            section = _trim_near_sentence("\n\n".join(segments), block_target)
            is_conclusion = block_index == len(raw_blocks) - 1 and len(raw_blocks) >= 4
            conclusion_floor = max(250, math.floor(block_target * 0.35))
            block_floor = conclusion_floor if is_conclusion else 250
            if len(section) < block_floor:
                raise ValueError(
                    f"장문 생성이 {block_index + 1}번째 전개 구간에서 목표 분량을 채우지 못했습니다. "
                    f"목표 {block_target:,}자, 실제 {len(section):,}자, "
                    f"유효 구간 {len(segments)}개입니다."
                )
            completed_sections.append(section)
            block_counts.append(len(section))

        body = "\n\n".join(completed_sections).strip()
        minimum_total = math.floor(target * LONG_FORM_MINIMUM_RATIO)
        if len(body) < minimum_total and len(completed_sections) >= 2:
            recovery_index = max(
                range(len(completed_sections) - 1),
                key=lambda index: budgets[index] - len(completed_sections[index]),
            )
            for attempt in range(LONG_FORM_MAX_CALLS_PER_BLOCK):
                body = "\n\n".join(completed_sections).strip()
                if len(body) >= minimum_total:
                    break
                recovery_section = completed_sections[recovery_index]
                remaining = minimum_total - len(body)
                recovery_focus = segment_foci[(attempt + 1) % (len(segment_foci) - 1)]
                recovery_payload = {
                    "long_form_contract": {
                        "mode": f"{mode}_length_recovery",
                        "block_number": recovery_index + 1,
                        "block_count": len(raw_blocks),
                        "block_target_characters": len(recovery_section) + remaining,
                        "block_minimum_characters": len(recovery_section) + remaining,
                        "current_character_count": len(recovery_section),
                        "remaining_characters": remaining,
                        "requested_new_characters": min(2400, max(900, remaining + 500)),
                        "segment_focus": recovery_focus,
                        "covered_paragraph_openings": [
                            paragraph[:120]
                            for paragraph in _markdown_blocks(
                                "\n\n".join(completed_sections)
                            )[-30:]
                        ],
                        "active_block": {
                            **raw_blocks[recovery_index],
                            "purpose": (
                                "결론을 반복하지 말고, 초안에서 아직 충분히 풀지 않은 다른 근거·"
                                "작동 원리·인과·한계를 골라 이 분석 구간에 삽입할 독립 문단을 쓴다."
                            ),
                        },
                        "next_block_purpose": raw_blocks[recovery_index + 1].get(
                            "purpose", "다음 전개로 이행한다."
                        ),
                    },
                    "previous_block_tail": completed_sections[
                        max(0, recovery_index - 1)
                    ][-1000:],
                    "current_block_text": recovery_section,
                    "source_material": source_payload,
                    "instruction": (
                        "이미 쓴 결론이나 기존 문단을 되풀이하지 말고, 이 분석 구간에 삽입할 "
                        f"새 한국어 문단만 출력하라. 이번 응답의 필수 초점: {recovery_focus}"
                    ),
                }
                result = await self.gateway.complete(
                    [
                        {"role": "system", "content": segment_prompt},
                        {
                            "role": "user",
                            "content": json.dumps(
                                recovery_payload, ensure_ascii=False, indent=2
                            ),
                        },
                    ],
                    role="writer",
                    temperature=temperature,
                    max_tokens=3500,
                    seed=(seed + len(results) + 1) if seed is not None else None,
                )
                results.append(result)
                segment = _unique_generated_text(
                    _remove_continuation_overlap(
                        recovery_section, _clean_generated_text(result.content)
                    ),
                    "\n\n".join(completed_sections),
                )
                if len(segment) < 40 or segment in recovery_section:
                    continue
                completed_sections[recovery_index] = (
                    f"{recovery_section}\n\n{segment}"
                ).strip()

            body = "\n\n".join(completed_sections).strip()
            block_counts = [len(section) for section in completed_sections]
        if len(body) < minimum_total:
            raise ValueError(
                f"장문 생성 결과가 목표 분량에 미달했습니다. "
                f"목표 {target:,}자, 최소 {minimum_total:,}자, 실제 {len(body):,}자입니다."
            )
        duplicate_count = _near_duplicate_count(body)
        if duplicate_count:
            raise ValueError(
                f"장문 생성 결과에서 유사 문단 {duplicate_count}개를 감지해 저장하지 않았습니다."
            )
        for block_index, section in enumerate(completed_sections):
            paragraph_plan_indexes.extend(
                [block_index] * len(_markdown_blocks(section))
            )
        return (
            _aggregate_calls(
                results,
                body,
                target=target,
                block_counts=block_counts,
            ),
            paragraph_plan_indexes,
        )

    def context_preview(self, db: Session, session: PlaybookSession) -> dict[str, Any]:
        pack = compile_context(db, session)
        session.evidence_pack_json = pack
        session.voice_example_ids = [
            str(example["id"]) for example in pack.get("style_examples", [])
        ]
        db.add(session)
        _record_stage(
            db,
            session,
            "COMPILE_CONTEXT",
            input_json={"concept_slots": session.concept_slots},
            output_json=pack,
        )
        db.commit()
        db.refresh(session)
        return pack

    def draft_body(self, db: Session, document: LoreDocument) -> str:
        blocks = list(
            db.scalars(
                select(LoreBlock)
                .where(LoreBlock.document_id == document.id)
                .order_by(LoreBlock.position)
            ).all()
        )
        if blocks:
            return "\n\n".join(
                block.content_markdown.strip() for block in blocks if block.content_markdown.strip()
            )
        return document.body_markdown.strip()

    def finalization_inputs(
        self,
        db: Session,
        document: LoreDocument,
        *,
        user_direction: str | None = None,
        writing_recipe_id: str | None = None,
        voice_profile_id: str | None | object = UNSET,
        voice_selection_mode: str | None = None,
        voice_example_ids: list[str] | None = None,
        output_profile: str | None = None,
        settings_json: dict[str, Any] | None = None,
    ) -> tuple[PlaybookSession, dict[str, Any], dict[str, Any], str]:
        if document.document_kind != "draft":
            raise ValueError("로어북 글이 아니라 편집 중인 초안을 선택하십시오.")
        if not document.session_id:
            raise ValueError("글 만들기 기록이 없는 문서는 전체 글 다듬기를 실행할 수 없습니다.")
        session = db.get(PlaybookSession, document.session_id)
        if not session:
            raise ValueError("이 원고를 만든 글 만들기 기록을 찾을 수 없습니다.")
        effective_recipe_id = writing_recipe_id or session.writing_recipe_id
        effective_profile = output_profile or session.output_profile
        effective_direction = session.user_direction if user_direction is None else user_direction
        effective_settings = {
            **(session.settings_json or {}),
            **(settings_json or {}),
        }
        writing_recipe = db.get(WritingRecipe, effective_recipe_id)
        if not writing_recipe or writing_recipe.project_id not in {None, document.project_id}:
            raise ValueError("선택한 전개 방식을 이 프로젝트에서 사용할 수 없습니다.")
        available_profiles = load_output_profiles()
        profile = next(
            (
                item
                for item in available_profiles
                if str(item.get("key")) == effective_profile
            ),
            None,
        )
        if not profile and available_profiles:
            raise ValueError("선택한 결과물 종류를 찾을 수 없습니다.")
        profile = profile or {"key": effective_profile, "name": effective_profile, "rules": {}}
        pack = compile_context(
            db,
            session,
            writing_recipe_id=effective_recipe_id,
            output_profile=effective_profile,
            user_direction=effective_direction,
            settings_json=effective_settings,
            voice_profile_id=voice_profile_id,
            voice_selection_mode=voice_selection_mode,
            voice_example_ids=voice_example_ids,
        )
        inputs = {
            "user_direction": effective_direction,
            "output_profile": {
                "key": effective_profile,
                "name": profile.get("name", effective_profile),
                "rules": profile.get("rules", {}),
            },
            "generation_settings": effective_settings,
            "writing_recipe": {
                "id": writing_recipe.id,
                "key": writing_recipe.key,
                "name": writing_recipe.name,
                "version": writing_recipe.version,
                "recipe": writing_recipe.recipe_json,
            },
            "voice_profile": pack.get("voice_profile"),
            "voice_selection_mode": pack.get("voice_selection_mode", "model_default"),
            "style_examples": [
                {
                    "id": example.get("id"),
                    "label": example.get("label"),
                    "excerpt_hash": example.get("excerpt_hash"),
                    "teaches": example.get("teaches", []),
                }
                for example in pack.get("style_examples", [])
            ],
        }
        draft = self.draft_body(db, document)
        return session, pack, inputs, draft

    def finalization_summary(self, db: Session, document: LoreDocument) -> dict[str, Any]:
        _, _, inputs, draft = self.finalization_inputs(db, document)
        lorebook_entry = db.scalar(
            select(LoreDocument).where(
                LoreDocument.document_kind == "lorebook",
                LoreDocument.source_document_id == document.id,
            )
        )
        if lorebook_entry and lorebook_entry.generation_inputs_json:
            inputs = lorebook_entry.generation_inputs_json
        current_hash = _stable_hash(draft)
        has_final = bool(lorebook_entry and lorebook_entry.body_markdown.strip())
        draft_changed = bool(
            has_final and lorebook_entry and lorebook_entry.source_draft_hash != current_hash
        )
        return {
            "source_document": document,
            "lorebook_entry": lorebook_entry,
            "status": "stale" if draft_changed else "ready" if has_final else "not_started",
            "draft_changed": draft_changed,
            "current_draft_hash": current_hash,
            "inputs": inputs,
        }

    async def finalize_document(
        self,
        db: Session,
        document: LoreDocument,
        *,
        instruction: str = "",
        refinement_json: dict[str, Any] | None = None,
        user_direction: str | None = None,
        writing_recipe_id: str | None = None,
        voice_profile_id: str | None | object = UNSET,
        voice_selection_mode: str | None = None,
        voice_example_ids: list[str] | None = None,
        output_profile: str | None = None,
        settings_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session, pack, inputs, draft = self.finalization_inputs(
            db,
            document,
            user_direction=user_direction,
            writing_recipe_id=writing_recipe_id,
            voice_profile_id=voice_profile_id,
            voice_selection_mode=voice_selection_mode,
            voice_example_ids=voice_example_ids,
            output_profile=output_profile,
            settings_json=settings_json,
        )
        if not draft:
            raise ValueError("다듬을 초안 내용이 없습니다.")
        refinement = _normalize_refinement(refinement_json)
        inputs["refinement"] = refinement
        draft_hash = _stable_hash(draft)
        plan = session.plan_json or {}
        original_target = int(plan.get("target_length") or _target_length(pack))
        if refinement["length_policy"] == "tighten":
            target = max(500, math.floor(len(draft) * 0.82))
        elif refinement["length_policy"] == "expand":
            target = max(original_target, math.ceil(len(draft) * 1.18))
        else:
            target = len(draft)
        payload = {
            "title": document.title,
            "editable_draft": draft,
            "original_writing_request": inputs,
            "article_plan": session.plan_json,
            "direction_cards": pack.get("direction_cards", []),
            "expression_design": {
                "voice_profile": pack.get("voice_profile"),
                "style_examples": pack.get("style_examples", []),
                "policy": {
                    "style_examples_are_non_factual": True,
                    "reference_names_are_forbidden": True,
                    "reference_phrases_must_not_be_copied": True,
                },
            },
            "fact_boundaries": {
                "locked_facts": pack.get("locked_facts", []),
                "open_questions": pack.get("open_questions", []),
                "forbidden_material": pack.get("forbidden_material", []),
                "selected_concepts": [
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "summary": item.get("summary", ""),
                    }
                    for item in pack.get("selected_concepts", [])
                ],
            },
            "revision_brief": refinement,
            "target_character_contract": {
                "original_target": original_target,
                "current_draft": len(draft),
                "target": target,
                "minimum": math.floor(target * LONG_FORM_MINIMUM_RATIO),
            },
            "final_pass_instruction": instruction,
            "instruction": "분석이나 작업 설명 없이 완성된 한국어 글 본문만 출력하라.",
        }
        system_prompt = load_prompt("finalizer.md")
        if target >= LONG_FORM_THRESHOLD:
            call_result, _ = await self._complete_long_form(
                system_prompt=system_prompt,
                source_payload=payload,
                plan=plan,
                target=target,
                temperature=0.48,
                seed=session.seed,
                mode=f"finalize_{refinement['length_policy']}",
            )
            body = call_result.content
        else:
            call_result = await self.gateway.complete(
                [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False, indent=2),
                    },
                ],
                role="writer",
                temperature=0.48,
                max_tokens=None,
                seed=session.seed,
            )
            body = _clean_generated_text(call_result.content)
        if not body:
            raise ValueError("Writer가 비어 있는 완성본을 반환했습니다.")
        if refinement["length_policy"] in {"preserve", "expand"} and len(body) < target * 0.7:
            raise ValueError(
                f"완성본이 선택한 분량 방향에 크게 못 미칩니다. "
                f"목표 {target:,}자, 실제 {len(body):,}자이므로 저장하지 않았습니다."
            )

        lorebook_entry = db.scalar(
            select(LoreDocument).where(
                LoreDocument.document_kind == "lorebook",
                LoreDocument.source_document_id == document.id,
            )
        )
        if not lorebook_entry:
            lorebook_entry = LoreDocument(
                project_id=document.project_id,
                session_id=session.id,
                writing_recipe_id=inputs["writing_recipe"]["id"],
                title=document.title,
                document_kind="lorebook",
                source_document_id=document.id,
            )
        lorebook_entry.title = document.title
        lorebook_entry.body_markdown = body
        lorebook_entry.body_json = _plain_document_json(body)
        lorebook_entry.writing_recipe_id = inputs["writing_recipe"]["id"]
        lorebook_entry.source_draft_hash = draft_hash
        lorebook_entry.generation_inputs_json = inputs
        lorebook_entry.published_at = datetime.now(UTC)
        lorebook_entry.status = "approved"
        db.add(lorebook_entry)
        db.flush()
        run = GenerationRun(
            project_id=document.project_id,
            session_id=session.id,
            document_id=lorebook_entry.id,
            task="finalize",
            model_role="writer",
            model=str(call_result.model),
            endpoint=str(call_result.endpoint),
            runtime="openai-compatible",
            prompt_components={
                "recipe": inputs["writing_recipe"].get("name"),
                "recipe_version": inputs["writing_recipe"].get("version"),
                "output_profile": inputs["output_profile"]["key"],
                "user_direction": inputs["user_direction"],
                "voice_profile_id": (inputs.get("voice_profile") or {}).get("id"),
                "voice_profile_version": (inputs.get("voice_profile") or {}).get("version"),
                "voice_example_ids": [item.get("id") for item in inputs.get("style_examples", [])],
                "refinement_priorities": refinement["priorities"],
            },
            selected_concept_ids=_selected_ids(session),
            direction_card_ids=session.direction_card_ids,
            params_json={
                **inputs["generation_settings"],
                "refinement": refinement,
                "final_pass_instruction": instruction,
                "target_characters": target,
                "actual_characters": len(body),
                "length_strategy": call_result.params.get("strategy", "single_call"),
                "model_call": call_result.audit_metadata(),
            },
            input_hash=_stable_hash(payload),
            input_json=payload,
            usage_json=call_result.usage,
            output_text=body,
        )
        db.add(run)
        db.flush()
        add_lore_revision(
            db,
            lorebook_entry,
            reason="final_coherence_pass",
            author_type="llm",
        )
        _record_stage(
            db,
            session,
            "FINAL_COHERENCE_PASS",
            input_json={
                "source_document_id": document.id,
                "lorebook_entry_id": lorebook_entry.id,
                "draft_hash": draft_hash,
                "reused_inputs": inputs,
                "final_pass_instruction": instruction,
            },
            output_json={
                "body_hash": _stable_hash(body),
                "character_count": len(body),
                "target_characters": target,
                "length_strategy": call_result.params.get("strategy", "single_call"),
            },
            run_id=run.id,
        )
        session.state = "finalized"
        db.add(session)
        db.commit()
        db.refresh(lorebook_entry)
        return {
            "source_document": document,
            "lorebook_entry": lorebook_entry,
            "status": "ready",
            "draft_changed": False,
            "current_draft_hash": draft_hash,
            "inputs": inputs,
        }

    async def plan(self, db: Session, session: PlaybookSession) -> dict[str, Any]:
        pack = compile_context(db, session)
        session.evidence_pack_json = pack
        _record_stage(
            db,
            session,
            "COMPILE_CONTEXT",
            input_json={"concept_slots": session.concept_slots},
            output_json=pack,
        )
        system_prompt = load_prompt("planner.md")
        user_prompt = json.dumps(pack, ensure_ascii=False, indent=2)
        call_result = await self.gateway.complete(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            role="utility",
            temperature=0.35,
            response_mode="json_schema",
            json_schema=PLAN_SCHEMA,
            schema_name="lore_article_plan",
            max_tokens=5000,
            seed=session.seed,
        )
        plan = _normalize_plan(_json_from_text(call_result.content), pack)

        session.plan_json = plan
        session.evidence_pack_json = pack
        session.state = "planned"
        db.add(session)
        run = GenerationRun(
            project_id=session.project_id,
            session_id=session.id,
            task="plan",
            model_role="utility",
            model=str(call_result.model),
            endpoint=str(call_result.endpoint),
            runtime="openai-compatible",
            prompt_components={
                "recipe": pack.get("writing_recipe", {}).get("key"),
                "recipe_version": pack.get("writing_recipe", {}).get("version"),
                "output_profile": session.output_profile,
                "voice_profile_id": (pack.get("voice_profile") or {}).get("id"),
                "voice_profile_version": (pack.get("voice_profile") or {}).get("version"),
            },
            selected_concept_ids=_selected_ids(session),
            direction_card_ids=session.direction_card_ids,
            params_json={
                **session.settings_json,
                "model_call": call_result.audit_metadata(),
            },
            input_hash=_stable_hash(pack),
            input_json=pack,
            usage_json=call_result.usage,
            output_text=json.dumps(plan, ensure_ascii=False),
        )
        db.add(run)
        db.flush()
        _record_stage(
            db,
            session,
            "SELECT_ANGLE",
            input_json={"direction_cards": pack.get("direction_cards", [])},
            output_json={"angle": plan.get("angle", "")},
            run_id=run.id,
        )
        _record_stage(db, session, "PLAN", input_json=pack, output_json=plan, run_id=run.id)
        _record_stage(
            db,
            session,
            "USER_EDITABLE_PLAN",
            input_json=plan,
            output_json={"editable": True, "plan": plan},
            run_id=run.id,
        )
        db.commit()
        db.refresh(session)
        return plan

    async def generate(self, db: Session, session: PlaybookSession) -> LoreDocument:
        pack = compile_context(db, session)
        plan = session.plan_json or await self.plan(db, session)

        system_prompt = load_prompt("writer.md")
        payload = {
            "context_pack": pack,
            "article_plan": plan,
            "instruction": "완성된 한국어 본문만 출력하라.",
        }
        target = int(plan.get("target_length") or _target_length(pack))
        paragraph_plan_indexes: list[int] = []
        if target >= LONG_FORM_THRESHOLD:
            call_result, paragraph_plan_indexes = await self._complete_long_form(
                system_prompt=system_prompt,
                source_payload=payload,
                plan=plan,
                target=target,
                temperature=0.72,
                seed=session.seed,
                mode="draft",
            )
            body = call_result.content
        else:
            call_result = await self.gateway.complete(
                [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False, indent=2),
                    },
                ],
                role="writer",
                temperature=0.72,
                max_tokens=None,
                seed=session.seed,
            )
            body = _clean_generated_text(call_result.content)

        title = str(plan.get("title") or "새 로어 문서")
        paragraphs = _markdown_blocks(body)
        plan_blocks = list(plan.get("blocks", []))
        body_nodes: list[dict[str, Any]] = []
        for index, paragraph in enumerate(paragraphs):
            plan_index = (
                paragraph_plan_indexes[index]
                if index < len(paragraph_plan_indexes)
                else min(index, len(plan_blocks) - 1)
            )
            plan_block = plan_blocks[plan_index] if plan_blocks else {}
            body_nodes.append(
                _block_json(
                    paragraph,
                    {
                        "rhetoricalMove": plan_block.get("move", "ANCHOR"),
                        "playbookStep": "DRAFT_BLOCKS",
                        "evidenceIds": plan_block.get("evidence_ids", []),
                        "certainty": "EVIDENCED" if plan_block.get("evidence_ids") else "CANDIDATE",
                        "sourceRole": "CANDIDATE",
                        "locked": False,
                    },
                )
            )
        recipe = db.get(WritingRecipe, session.writing_recipe_id)
        document = LoreDocument(
            project_id=session.project_id,
            session_id=session.id,
            writing_recipe_id=session.writing_recipe_id,
            title=title,
            body_markdown=body,
            body_json={"type": "doc", "content": body_nodes},
            generation_inputs_json={
                "user_direction": session.user_direction,
                "writing_recipe": {
                    "id": recipe.id if recipe else session.writing_recipe_id,
                    "key": pack.get("writing_recipe", {}).get("key"),
                    "version": pack.get("writing_recipe", {}).get("version"),
                    "name": pack.get("writing_recipe", {}).get("name"),
                },
                "output_profile": {
                    "key": session.output_profile,
                    "name": pack.get("output_profile", {}).get("name", session.output_profile),
                    "rules": pack.get("output_profile", {}).get("rules", {}),
                },
                "generation_settings": session.settings_json,
                "voice_profile": pack.get("voice_profile"),
                "voice_selection_mode": pack.get("voice_selection_mode", "model_default"),
                "style_examples": [
                    {
                        "id": example.get("id"),
                        "label": example.get("label"),
                        "excerpt_hash": example.get("excerpt_hash"),
                    }
                    for example in pack.get("style_examples", [])
                ],
            },
            status="draft",
        )
        db.add(document)
        db.flush()
        db.add(
            LoreRevision(
                document_id=document.id,
                body_markdown=body,
                body_json=document.body_json,
                reason="initial_generation",
                author_type="llm",
            )
        )
        run = GenerationRun(
                project_id=session.project_id,
                session_id=session.id,
                document_id=document.id,
                task="draft",
                model_role="writer",
                model=str(call_result.model),
                endpoint=str(call_result.endpoint),
                runtime="openai-compatible",
                prompt_components={
                    "recipe": pack.get("writing_recipe", {}).get("key"),
                    "recipe_version": pack.get("writing_recipe", {}).get("version"),
                    "output_profile": session.output_profile,
                    "voice_profile_id": (pack.get("voice_profile") or {}).get("id"),
                    "voice_profile_version": (pack.get("voice_profile") or {}).get("version"),
                    "voice_example_ids": [item.get("id") for item in pack.get("style_examples", [])],
                },
                selected_concept_ids=_selected_ids(session),
                direction_card_ids=session.direction_card_ids,
                params_json={
                    **session.settings_json,
                    "target_characters": target,
                    "actual_characters": len(body),
                    "length_strategy": call_result.params.get("strategy", "single_call"),
                    "model_call": call_result.audit_metadata(),
                },
                input_hash=_stable_hash({"pack": pack, "plan": plan}),
                input_json={"context_pack": pack, "article_plan": plan},
                usage_json=call_result.usage,
                output_text=body,
            )
        db.add(run)
        db.flush()
        for index, paragraph in enumerate(paragraphs):
            plan_index = (
                paragraph_plan_indexes[index]
                if index < len(paragraph_plan_indexes)
                else min(index, len(plan_blocks) - 1)
            )
            plan_block = plan_blocks[plan_index] if plan_blocks else {}
            db.add(
                LoreBlock(
                    document_id=document.id,
                    position=index,
                    content_markdown=paragraph,
                    content_json=body_nodes[index],
                    rhetorical_move=plan_block.get("move", "ANCHOR"),
                    evidence_ids=plan_block.get("evidence_ids", []),
                    certainty="EVIDENCED" if plan_block.get("evidence_ids") else "CANDIDATE",
                    source_role="CANDIDATE",
                    generation_run_id=run.id,
                )
            )
        _record_stage(
            db,
            session,
            "DRAFT_BLOCKS",
            input_json={"plan": plan},
            output_json={
                "document_id": document.id,
                "block_count": len(paragraphs),
                "target_characters": target,
                "actual_characters": len(body),
                "length_strategy": call_result.params.get("strategy", "single_call"),
            },
            run_id=run.id,
        )
        _record_stage(
            db,
            session,
            "COHERENCE_PASS",
            input_json={"block_count": len(paragraphs)},
            output_json={"body_hash": _stable_hash(body)},
            run_id=run.id,
        )
        session.state = "generated"
        db.add(session)
        db.commit()
        findings = run_audits(db, document, session, pack)
        for audit_type, step in (
            ("CANON", "CANON_AUDIT"),
            ("DISCOURSE", "DISCOURSE_AUDIT"),
            ("STYLE", "STYLE_AUDIT"),
        ):
            items = [item for item in findings if item.audit_type == audit_type]
            _record_stage(
                db,
                session,
                step,
                input_json={"document_id": document.id},
                output_json={"finding_ids": [item.id for item in items]},
                run_id=run.id,
            )
        _record_stage(
            db,
            session,
            "SAVE_REVISION",
            input_json={"document_id": document.id},
            output_json={"revision_number": 1},
            run_id=run.id,
        )
        db.commit()
        db.refresh(document)
        return document
