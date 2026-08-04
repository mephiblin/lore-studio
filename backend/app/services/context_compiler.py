from __future__ import annotations

from collections import OrderedDict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConceptPage, DirectionCard, PlaybookSession, Project, WritingRecipe

ROLE_FACT = {"PROJECT_CANON", "DRAFT_SETTING", "CANON_EVIDENCE", "SECONDARY_INTERPRETATION"}
ROLE_REFERENCE = {"DISCOURSE_REFERENCE", "INSPIRATION"}


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


def compile_context(db: Session, session: PlaybookSession) -> dict[str, Any]:
    project = db.get(Project, session.project_id)
    recipe = db.get(WritingRecipe, session.writing_recipe_id)
    if not project or not recipe:
        raise ValueError("프로젝트 또는 집필 레시피를 찾을 수 없습니다.")

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

    context_depth = str((session.settings_json or {}).get("context_depth", "balanced"))
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
        "user_direction": session.user_direction,
        "writing_recipe": recipe.recipe_json,
        "output_profile": session.output_profile,
        "generation_settings": session.settings_json,
        "seed": session.seed,
        "warnings": warnings,
        "policy": {
            "reference_facts_are_forbidden": True,
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
