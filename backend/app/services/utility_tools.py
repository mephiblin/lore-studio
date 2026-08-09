from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from app.services.model_gateway import ModelCallResult, ModelGateway

DIRECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["goals", "sequence", "must_include", "avoid", "ending_preference"],
    "properties": {
        "goals": {"type": "array", "items": {"type": "string"}},
        "sequence": {"type": "array", "items": {"type": "string"}},
        "must_include": {"type": "array", "items": {"type": "string"}},
        "avoid": {"type": "array", "items": {"type": "string"}},
        "ending_preference": {"type": "string"},
        "compatible_tags": {"type": "array", "items": {"type": "string"}},
        "incompatible_tags": {"type": "array", "items": {"type": "string"}},
    },
}

CANDIDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "category_key", "candidate_sentence", "source_excerpt"],
                "properties": {
                    "title": {"type": "string"},
                    "category_key": {"type": "string"},
                    "candidate_sentence": {"type": "string"},
                    "summary": {"type": "string"},
                    "source_excerpt": {"type": "string"},
                    "related_page_ids": {"type": "array", "items": {"type": "string"}},
                    "conflict_risk": {"type": "string"},
                },
            },
        }
    },
}

VOICE_PROFILE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "reader_effect",
        "sentence_rhythm",
        "description_rules",
        "dialogue_rules",
        "figurative_language",
        "paragraph_rules",
        "avoid_patterns",
        "best_for",
        "audit_rules",
        "compatibility",
    ],
    "properties": {
        "reader_effect": {"type": "string"},
        "sentence_rhythm": {"type": "array", "items": {"type": "string"}},
        "description_rules": {"type": "array", "items": {"type": "string"}},
        "dialogue_rules": {"type": "array", "items": {"type": "string"}},
        "figurative_language": {"type": "array", "items": {"type": "string"}},
        "paragraph_rules": {"type": "array", "items": {"type": "string"}},
        "avoid_patterns": {"type": "array", "items": {"type": "string"}},
        "best_for": {"type": "array", "items": {"type": "string"}},
        "audit_rules": {"type": "array", "items": {"type": "string"}},
        "compatibility": {
            "type": "object",
            "additionalProperties": False,
            "required": ["viewpoints", "tenses"],
            "properties": {
                "viewpoints": {"type": "array", "items": {"type": "string"}},
                "tenses": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}

REFERENCE_RECIPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["required_moves", "optional_moves", "planner_rules", "audit_rules", "best_for"],
    "properties": {
        "required_moves": {"type": "array", "items": {"type": "string"}},
        "optional_moves": {"type": "array", "items": {"type": "string"}},
        "planner_rules": {"type": "array", "items": {"type": "string"}},
        "audit_rules": {"type": "array", "items": {"type": "string"}},
        "best_for": {"type": "string"},
    },
}

REFERENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["paragraphs", "recipe_candidate", "voice_candidate", "similarity_risks"],
    "properties": {
        "paragraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["index", "primary_move", "secondary_move", "scale", "certainty", "ending"],
                "properties": {
                    "index": {"type": "integer"},
                    "primary_move": {"type": "string"},
                    "secondary_move": {"type": "string"},
                    "scale": {"type": "string"},
                    "certainty": {"type": "string"},
                    "tension": {"type": "integer"},
                    "sentence_length_pattern": {"type": "string"},
                    "ending": {"type": "string"},
                },
            },
        },
        "recipe_candidate": REFERENCE_RECIPE_SCHEMA,
        "voice_candidate": VOICE_PROFILE_SCHEMA,
        "similarity_risks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["category", "description", "severity"],
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["FACT_BLEED", "FIGURATIVE_COPY", "SINGLE_EXAMPLE_OVERFIT"],
                    },
                    "description": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                },
            },
        },
    },
}

VISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["caption", "people", "places", "objects", "tags", "uncertainties"],
    "properties": {
        "caption": {"type": "string"},
        "people": {"type": "array", "items": {"type": "string"}},
        "places": {"type": "array", "items": {"type": "string"}},
        "objects": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
}

WRITING_BOUNDARY_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["text", "source_excerpt"],
    "properties": {
        "text": {"type": "string", "minLength": 1},
        "source_excerpt": {"type": "string", "minLength": 1},
    },
}

WRITING_BOUNDARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["locked_facts", "open_questions", "forbidden_changes"],
    "properties": {
        "locked_facts": {"type": "array", "items": WRITING_BOUNDARY_ITEM_SCHEMA},
        "open_questions": {"type": "array", "items": WRITING_BOUNDARY_ITEM_SCHEMA},
        "forbidden_changes": {"type": "array", "items": WRITING_BOUNDARY_ITEM_SCHEMA},
    },
}

PROSE_AUDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["issues", "strengths", "uncertainties"],
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["block_id", "start_text", "category", "reason", "severity", "profile_rule"],
                "properties": {
                    "block_id": {"type": "string"},
                    "start_text": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "REPETITION",
                            "RHYTHM_FLATNESS",
                            "ABSTRACT_EMOTION",
                            "DIALOGUE_VOICE_COLLISION",
                            "EXPOSITION_OVERLOAD",
                            "FIGURATIVE_OVERLOAD",
                            "CLICHE_OR_SLOP",
                            "REFERENCE_OVERLAP",
                            "PROFILE_CONFLICT",
                        ],
                    },
                    "reason": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "warning", "error"]},
                    "profile_rule": {"type": "string"},
                },
            },
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
}


def parse_object(value: str) -> dict[str, Any]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value, re.DOTALL)
        if not match:
            raise ValueError("Utility 모델 응답에서 JSON 객체를 찾을 수 없습니다.") from None
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Utility 모델 응답은 JSON 객체여야 합니다.")
    return data


async def suggest_direction(gateway: ModelGateway, body: str) -> tuple[dict[str, Any], ModelCallResult]:
    result = await gateway.complete(
        [
            {
                "role": "system",
                "content": "사용자의 프로젝트 집필 지침 원문을 바꾸지 말고 목표·순서·필수·회피·결말 선호로 구조화하라.",
            },
            {"role": "user", "content": body},
        ],
        role="utility",
        temperature=0.1,
        max_tokens=1200,
        response_mode="json_schema",
        json_schema=DIRECTION_SCHEMA,
        schema_name="direction_card_rules",
    )
    return parse_object(result.content), result


async def suggest_writing_boundaries(
    gateway: ModelGateway,
    *,
    title: str,
    body: str,
    existing_boundaries: dict[str, list[str]],
) -> tuple[dict[str, Any], ModelCallResult]:
    payload = {
        "title": title,
        "body": body,
        "existing_boundaries": existing_boundaries,
        "rules": [
            "본문에 명시되거나 직접 뒷받침되는 내용만 제안한다.",
            "locked_facts에는 원고에서 반드시 참으로 유지해야 하는 사실을 간결한 평서문으로 적는다.",
            "open_questions에는 아직 정답이나 정체를 공개하지 않아야 하는 의문만 적는다.",
            "forbidden_changes에는 본문을 무너뜨리는 금지된 변경이나 전개만 적고 locked_facts를 반복하지 않는다.",
            "근거가 불충분하면 해당 목록을 비워 둔다.",
            "각 항목의 source_excerpt에는 판단 근거가 된 본문의 짧은 구절을 그대로 적는다.",
            "기존 항목과 같은 뜻의 제안은 반복하지 않는다.",
        ],
    }
    result = await gateway.complete(
        [
            {
                "role": "system",
                "content": (
                    "세계관 자료 본문에서 원고 작성 경계를 추출한다. 새로운 설정을 창작하거나 "
                    "모호한 부분을 사실로 확정하지 않는다. 출력은 사용자가 검토할 제안이며 자동 저장되지 않는다."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        role="utility",
        temperature=0.1,
        max_tokens=1800,
        response_mode="json_schema",
        json_schema=WRITING_BOUNDARY_SCHEMA,
        schema_name="writing_boundary_suggestion",
    )
    return parse_object(result.content), result


async def audit_prose(
    gateway: ModelGateway,
    *,
    blocks: list[dict[str, str]],
    voice_profile: dict[str, Any] | None,
    deterministic_findings: list[dict[str, Any]],
) -> tuple[dict[str, Any], ModelCallResult]:
    payload = {
        "blocks": blocks,
        "voice_profile": voice_profile,
        "deterministic_findings": deterministic_findings,
        "rules": [
            "세계관 사실과 사건 순서를 평가하거나 바꾸지 않는다.",
            "문학적 취향을 정답처럼 단정하지 않고 검토 가치가 있는 문제만 제안한다.",
            "문제가 있는 block_id를 그대로 반환한다.",
            "문체 프로필이 없으면 일반적인 반복·추상 감정·설명 과밀만 점검한다.",
            "원고 수정문을 만들지 않는다.",
        ],
    }
    result = await gateway.complete(
        [
            {
                "role": "system",
                "content": (
                    "한국어 산문의 필력 점검자다. 결정론 검사 결과를 참고하되 그대로 반복하지 말고, "
                    "독자가 실제로 느낄 리듬·묘사·대화·설명 문제를 좁게 찾는다. 결과는 검토 후보이며 자동 수정하지 않는다."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        role="utility",
        temperature=0.1,
        max_tokens=2400,
        response_mode="json_schema",
        json_schema=PROSE_AUDIT_SCHEMA,
        schema_name="prose_audit",
    )
    return parse_object(result.content), result


async def extract_candidates(
    gateway: ModelGateway,
    *,
    body: str,
    known_pages: list[dict[str, Any]],
    categories: list[dict[str, str]],
) -> tuple[dict[str, Any], ModelCallResult]:
    payload = {
        "known_pages": known_pages,
        "project_categories": categories,
        "draft": body,
        "rules": [
            "원고에 새로 등장했지만 알려진 페이지에 없는 설정만 후보로 제안한다.",
            "후보는 확정 사실이 아니며 자동 정사 승격 대상이 아니다.",
            "category_key는 project_categories에 있는 key 중 하나만 사용한다.",
        ],
    }
    schema = deepcopy(CANDIDATE_SCHEMA)
    category_keys = [category["key"] for category in categories]
    schema["properties"]["candidates"]["items"]["properties"]["category_key"]["enum"] = category_keys
    result = await gateway.complete(
        [
            {"role": "system", "content": "로어 원고에서 검토할 새 설정 후보를 추출한다."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        role="utility",
        temperature=0.1,
        max_tokens=2400,
        response_mode="json_schema",
        json_schema=schema,
        schema_name="concept_candidates",
    )
    return parse_object(result.content), result


async def analyze_reference(gateway: ModelGateway, body: str) -> tuple[dict[str, Any], ModelCallResult]:
    result = await gateway.complete(
        [
            {
                "role": "system",
                "content": (
                    "참고 글의 사실·고유명사를 재사용하지 말고 문단의 수사적 이동, 스케일, 확실성, "
                    "긴장, 문장 리듬과 종결 방식만 분석한다. recipe_candidate와 voice_candidate에는 "
                    "원문의 고유명사와 긴 문장을 절대 넣지 않는다. voice_candidate는 작가 이름이나 "
                    "줄거리 요약이 아니라 측정 가능한 독서 인상·문장 호흡·묘사·대화·비유·문단 규칙만 "
                    "일반화한다. 확신하지 못한 항목은 빈 목록으로 둔다. Move는 ORIENT,NARROW,ANCHOR,"
                    "COMPLICATE,COMPARE,EXEMPLIFY,ESCALATE,INTERPRET,WITHHOLD,TURN,STING 중 선택한다."
                ),
            },
            {"role": "user", "content": body},
        ],
        role="utility",
        temperature=0.1,
        max_tokens=3200,
        response_mode="json_schema",
        json_schema=REFERENCE_SCHEMA,
        schema_name="reference_analysis",
    )
    return parse_object(result.content), result


async def analyze_image(
    gateway: ModelGateway, image_data_url: str, instruction: str
) -> tuple[dict[str, Any], ModelCallResult]:
    result = await gateway.complete(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": instruction
                        or "이미지를 한국어로 설명하고 인물·장소·물건·검색 태그를 제안하라. 불확실한 내용은 확정하지 않는다.",
                    },
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
        role="vision",
        temperature=0.1,
        max_tokens=1400,
        response_mode="json_schema",
        json_schema=VISION_SCHEMA,
        schema_name="image_concept_analysis",
    )
    return parse_object(result.content), result
