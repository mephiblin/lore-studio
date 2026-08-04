from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, ConceptPage

AUTHORITY_STATES = {"CANDIDATE", "DRAFT_SETTING", "PROJECT_CANON"}
USAGE_ROLES = {
    "PROJECT_CANON",
    "DRAFT_SETTING",
    "CANON_EVIDENCE",
    "SECONDARY_INTERPRETATION",
    "INSPIRATION",
    "DISCOURSE_REFERENCE",
    "CANDIDATE",
    "REJECTED",
}
ROLE_ALIASES = {
    "SOURCE_EVIDENCE": "CANON_EVIDENCE",
    "INSPIRATION_ONLY": "INSPIRATION",
}
ALLOWED_TRANSITIONS = {
    ("CANDIDATE", "DRAFT_SETTING"),
    ("DRAFT_SETTING", "PROJECT_CANON"),
}


class AuthorityTransitionError(ValueError):
    pass


def canonical_role(value: str) -> str:
    role = ROLE_ALIASES.get(value, value)
    if role not in USAGE_ROLES:
        raise AuthorityTransitionError(f"지원하지 않는 사용 역할입니다: {value}")
    return role


def snapshot_page(page: ConceptPage) -> dict[str, Any]:
    return {
        "id": page.id,
        "project_id": page.project_id,
        "title": page.title,
        "usage_role": page.usage_role,
        "authority_state": page.authority_state,
        "status": page.status,
    }


def promote_page(
    db: Session,
    page: ConceptPage,
    *,
    target_state: str,
    reason: str,
) -> ConceptPage:
    if target_state not in AUTHORITY_STATES:
        raise AuthorityTransitionError(f"지원하지 않는 권위 상태입니다: {target_state}")
    transition = (page.authority_state, target_state)
    if transition not in ALLOWED_TRANSITIONS:
        raise AuthorityTransitionError(
            f"{page.authority_state}에서 {target_state}(으)로 직접 승격할 수 없습니다. "
            "CANDIDATE → DRAFT_SETTING → PROJECT_CANON 순서를 지켜야 합니다."
        )
    before = snapshot_page(page)
    page.authority_state = target_state
    page.usage_role = target_state
    db.add(page)
    db.add(
        AuditLog(
            project_id=page.project_id,
            action="PROMOTE_AUTHORITY",
            entity_type="ConceptPage",
            entity_id=page.id,
            before_json=before,
            after_json=snapshot_page(page),
            reason=reason,
        )
    )
    db.commit()
    db.refresh(page)
    return page
