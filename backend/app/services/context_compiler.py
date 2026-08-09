from __future__ import annotations

import json
import math
from collections import OrderedDict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ConceptPage,
    DirectionCard,
    PlaybookSession,
    Project,
    VoiceProfile,
    VoiceProfileExample,
    WritingRecipe,
)

ROLE_FACT = {"PROJECT_CANON", "DRAFT_SETTING", "CANON_EVIDENCE", "SECONDARY_INTERPRETATION"}
ROLE_REFERENCE = {"DISCOURSE_REFERENCE", "INSPIRATION"}
VOICE_PROFILE_TOKEN_BUDGET = 900
STYLE_EXAMPLE_TOKEN_BUDGET = 1200
STYLE_EXAMPLE_MAX_COUNT = 5
UNSET = object()


def tiptap_to_text(node: Any) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(filter(None, (tiptap_to_text(item) for item in node)))
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return str(node.get("text", ""))
    content = node.get("content", [])
    text = tiptap_to_text(content)
    if node.get("type") in {"paragraph", "heading", "blockquote", "listItem"}:
        return text + "\n"
    return text


def _ordered_unique(values: list[str]) -> list[str]:
    return list(OrderedDict.fromkeys(values))


def _body_limit(context_depth: str) -> int:
    return {
        "core": 0,
        "balanced": 3000,
        "wide": 8000,
        "max": 16000,
    }.get(context_depth, 3000)


def _estimate_input_tokens(value: Any) -> int:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return max(1, math.ceil(len(text) / 2))


def _fit_voice_profile(profile_json: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    ordered_fields = (
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
    )
    fitted: dict[str, Any] = {}
    excluded: list[str] = []
    for field in ordered_fields:
        value = profile_json.get(field)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            accepted: list[Any] = []
            for item in value:
                candidate = {**fitted, field: [*accepted, item]}
                if _estimate_input_tokens(candidate) > VOICE_PROFILE_TOKEN_BUDGET:
                    excluded.append(f"{field}:token_budget")
                    break
                accepted.append(item)
            if accepted:
                fitted[field] = accepted
            continue
        candidate = {**fitted, field: value}
        if _estimate_input_tokens(candidate) <= VOICE_PROFILE_TOKEN_BUDGET:
            fitted[field] = value
        else:
            excluded.append(f"{field}:token_budget")
    return fitted, excluded


def _compile_voice_context(
    db: Session,
    session: PlaybookSession,
    *,
    profile_id: str | None,
    selection_mode: str,
    requested_example_ids: list[str],
    generation_settings: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, str]], list[str]]:
    if profile_id is None:
        return None, [], [], []
    profile = db.get(VoiceProfile, profile_id)
    if (
        not profile
        or profile.project_id not in {None, session.project_id}
        or profile.status not in {"APPROVED", "DEPRECATED"}
    ):
        raise ValueError("현재 프로젝트에서 사용할 수 없는 문체 프로필입니다.")

    fitted_profile, profile_exclusions = _fit_voice_profile(profile.profile_json or {})
    warnings = [f"문체 프로필 일부가 입력 예산으로 제외됨: {item}" for item in profile_exclusions]
    voice_pack = {
        "id": profile.id,
        "key": profile.key,
        "version": profile.version,
        "name": profile.name,
        "description": profile.description,
        "profile": fitted_profile,
        "input_tokens_estimate": _estimate_input_tokens(fitted_profile),
        "fact_eligible": False,
    }

    examples = list(
        db.scalars(
            select(VoiceProfileExample).where(
                VoiceProfileExample.voice_profile_id == profile.id,
                VoiceProfileExample.status == "ACTIVE",
            )
        ).all()
    )
    allowed = {
        example.id: example
        for example in examples
        if example.use_in_generation and example.rights_basis != "ANALYSIS_ONLY"
    }
    excluded: list[dict[str, str]] = [
        {"id": example.id, "reason": "analysis_only_or_disabled"}
        for example in examples
        if example.id not in allowed
    ]

    if selection_mode == "manual":
        missing = [example_id for example_id in requested_example_ids if example_id not in allowed]
        if missing:
            raise ValueError("선택한 문체 예시가 비활성화되었거나 생성 입력 권한이 없습니다.")
        ordered = [allowed[example_id] for example_id in requested_example_ids]
    else:
        viewpoint = str(generation_settings.get("viewpoint", ""))
        tense = str(generation_settings.get("tense", ""))
        compatibility = profile.profile_json.get("compatibility", {}) or {}
        viewpoint_match = viewpoint in compatibility.get("viewpoints", [])
        tense_match = tense in compatibility.get("tenses", [])
        ordered = sorted(
            allowed.values(),
            key=lambda example: (
                -int(viewpoint_match),
                -int(tense_match),
                example.position,
                example.id,
            ),
        )[:3]

    compiled: list[dict[str, Any]] = []
    used_tokens = 0
    for example in ordered[:STYLE_EXAMPLE_MAX_COUNT]:
        item_tokens = _estimate_input_tokens(example.excerpt)
        if item_tokens > STYLE_EXAMPLE_TOKEN_BUDGET // 2:
            excluded.append({"id": example.id, "reason": "single_example_budget"})
            continue
        if used_tokens + item_tokens > STYLE_EXAMPLE_TOKEN_BUDGET:
            excluded.append({"id": example.id, "reason": "total_example_budget"})
            continue
        compiled.append(
            {
                "id": example.id,
                "label": example.label,
                "excerpt": example.excerpt,
                "excerpt_hash": example.excerpt_hash,
                "teaches": example.teaches_json,
                "scene_tags": example.scene_tags,
                "input_tokens_estimate": item_tokens,
                "fact_eligible": False,
            }
        )
        used_tokens += item_tokens
    return voice_pack, compiled, excluded, warnings


def compile_context(
    db: Session,
    session: PlaybookSession,
    *,
    writing_recipe_id: str | None = None,
    output_profile: str | None = None,
    user_direction: str | None = None,
    settings_json: dict[str, Any] | None = None,
    voice_profile_id: str | None | object = UNSET,
    voice_selection_mode: str | None = None,
    voice_example_ids: list[str] | None = None,
) -> dict[str, Any]:
    project = db.get(Project, session.project_id)
    recipe = db.get(WritingRecipe, writing_recipe_id or session.writing_recipe_id)
    if not project or not recipe:
        raise ValueError("프로젝트 또는 집필 레시피를 찾을 수 없습니다.")
    if not recipe.approved or recipe.project_id not in {None, session.project_id}:
        raise ValueError("현재 프로젝트에서 사용할 수 없는 전개 방식입니다.")

    selected_ids: list[str] = []
    slot_map = session.concept_slots or {}
    for ids in slot_map.values():
        selected_ids.extend(ids or [])
    selected_ids = _ordered_unique(selected_ids)

    pages: list[ConceptPage] = []
    if selected_ids:
        rows = db.scalars(
            select(ConceptPage).where(
                ConceptPage.id.in_(selected_ids), ConceptPage.project_id == session.project_id
            )
        ).all()
        by_id = {page.id: page for page in rows}
        pages = [by_id[page_id] for page_id in selected_ids if page_id in by_id]

    cards: list[DirectionCard] = []
    if session.direction_card_ids:
        rows = db.scalars(
            select(DirectionCard).where(
                DirectionCard.id.in_(session.direction_card_ids),
                DirectionCard.project_id == session.project_id,
            )
        ).all()
        by_id = {card.id: card for card in rows}
        cards = [by_id[card_id] for card_id in session.direction_card_ids if card_id in by_id]

    effective_settings = session.settings_json if settings_json is None else settings_json
    context_depth = str((effective_settings or {}).get("context_depth", "balanced"))
    body_limit = _body_limit(context_depth)

    facts: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    candidate_material: list[dict[str, Any]] = []
    locked_facts: list[dict[str, str]] = []
    open_questions: list[dict[str, str]] = []
    forbidden_changes: list[dict[str, str]] = []
    warnings: list[str] = []
    namespaces: set[str] = set()

    roles_by_page: dict[str, list[str]] = {}
    for slot, ids in slot_map.items():
        for page_id in ids or []:
            roles_by_page.setdefault(page_id, []).append(slot)

    for page in pages:
        namespaces.add(page.namespace)
        body_text = tiptap_to_text(page.body_json).strip()
        if body_limit == 0:
            body_text = ""
        elif len(body_text) > body_limit:
            body_text = body_text[:body_limit] + "\n[…본문 일부 생략…]"

        item = {
            "id": page.id,
            "title": page.title,
            "category": page.category_key,
            "tags": page.tags,
            "usage_role": page.usage_role,
            "status": page.status,
            "namespace": page.namespace,
            "era": page.era,
            "continuity": page.continuity,
            "playbook_roles": roles_by_page.get(page.id, []),
            "summary": page.summary,
            "body": body_text,
        }
        if page.status == "rejected" or page.usage_role == "REJECTED":
            warnings.append(f"폐기된 페이지가 선택되어 제외됨: {page.title}")
            continue
        if page.usage_role == "DISCOURSE_REFERENCE":
            references.append(
                {
                    **item,
                    "summary": "",
                    "body": "",
                    "approved_analysis": (page.properties_json or {}).get("approved_analysis", {}),
                    "fact_eligible": False,
                }
            )
        elif page.usage_role == "INSPIRATION":
            references.append({**item, "body": "", "fact_eligible": False})
        elif page.usage_role == "CANDIDATE":
            candidate_material.append({**item, "fact_eligible": False})
        elif page.usage_role in ROLE_FACT:
            facts.append(item)
            locked_facts.extend(
                {"page_id": page.id, "page_title": page.title, "fact": fact}
                for fact in page.locked_facts
            )
            open_questions.extend(
                {"page_id": page.id, "page_title": page.title, "question": question}
                for question in page.open_questions
            )
            forbidden_changes.extend(
                {"page_id": page.id, "page_title": page.title, "rule": rule}
                for rule in page.forbidden_changes
            )

    factual_namespaces = {item["namespace"] for item in facts}
    if len(factual_namespaces) > 1:
        warnings.append("서로 다른 네임스페이스의 사실 자료가 함께 선택되었습니다. 의도적인 크로스오버인지 확인하십시오.")
    if project.universe_namespace and factual_namespaces and project.universe_namespace not in factual_namespaces:
        warnings.append("선택된 사실 자료의 네임스페이스가 프로젝트 기본 네임스페이스와 다릅니다.")

    effective_voice_profile_id = (
        session.voice_profile_id if voice_profile_id is UNSET else voice_profile_id
    )
    effective_voice_mode = voice_selection_mode or (
        session.voice_selection_mode if voice_profile_id is UNSET else (
            "model_default" if effective_voice_profile_id is None else "profile_default"
        )
    )
    effective_example_ids = (
        session.voice_example_ids if voice_example_ids is None else voice_example_ids
    )
    voice_profile, style_examples, excluded_style_examples, voice_warnings = _compile_voice_context(
        db,
        session,
        profile_id=effective_voice_profile_id if isinstance(effective_voice_profile_id, str) else None,
        selection_mode=effective_voice_mode,
        requested_example_ids=effective_example_ids,
        generation_settings=effective_settings or {},
    )
    warnings.extend(voice_warnings)

    pack = {
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "universe_namespace": project.universe_namespace,
            "settings": project.settings_json,
        },
        "selected_concepts": facts,
        "discourse_or_inspiration_references": references,
        "candidate_material": candidate_material,
        "locked_facts": locked_facts,
        "open_questions": open_questions,
        "forbidden_material": forbidden_changes,
        "direction_cards": [
            {
                "id": card.id,
                "title": card.title,
                "body": card.body,
                "parsed_rules": card.parsed_rules,
                "priority_weight": card.weight,
            }
            for card in cards
        ],
        "user_direction": session.user_direction if user_direction is None else user_direction,
        "writing_recipe": recipe.recipe_json,
        "voice_profile": voice_profile,
        "style_examples": style_examples,
        "excluded_style_examples": excluded_style_examples,
        "voice_selection_mode": effective_voice_mode,
        "output_profile": output_profile or session.output_profile,
        "generation_settings": effective_settings,
        "seed": session.seed,
        "warnings": warnings,
        "policy": {
            "reference_facts_are_forbidden": True,
            "style_examples_are_non_factual": True,
            "reference_names_are_forbidden": True,
            "reference_phrases_must_not_be_copied": True,
            "generated_concepts_require_user_approval": True,
            "authority_order": [
                "CURRENT_USER_DIRECTION",
                "PROJECT_CANON_AND_LOCKED_FACTS",
                "DRAFT_SETTING",
                "CANON_EVIDENCE",
                "ALLOWED_INFERENCE",
                "MODEL_CREATION",
            ],
        },
    }
    return pack
