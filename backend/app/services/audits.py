from __future__ import annotations

import re
from collections import Counter
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AuditFinding, LoreBlock, LoreDocument, PlaybookSession


def run_audits(
    db: Session,
    document: LoreDocument,
    session: PlaybookSession,
    context_pack: dict[str, Any],
) -> list[AuditFinding]:
    db.execute(
        delete(AuditFinding).where(
            AuditFinding.document_id == document.id,
            AuditFinding.audit_type.in_(["CANON", "DISCOURSE", "STYLE"]),
        )
    )
    blocks = list(
        db.scalars(
            select(LoreBlock)
            .where(LoreBlock.document_id == document.id)
            .order_by(LoreBlock.position)
        ).all()
    )
    findings: list[AuditFinding] = []

    forbidden = [item["rule"] for item in context_pack.get("forbidden_material", [])]
    for block in blocks:
        if not block.evidence_ids and block.certainty != "CANDIDATE":
            findings.append(
                AuditFinding(
                    project_id=document.project_id,
                    document_id=document.id,
                    block_id=block.id,
                    audit_type="CANON",
                    severity="warning",
                    code="MISSING_EVIDENCE",
                    message="근거 페이지 없이 확정적으로 표시된 문단입니다.",
                    evidence_json={"certainty": block.certainty},
                )
            )
        for rule in forbidden:
            if rule and rule.casefold() in block.content_markdown.casefold():
                findings.append(
                    AuditFinding(
                        project_id=document.project_id,
                        document_id=document.id,
                        block_id=block.id,
                        audit_type="CANON",
                        severity="error",
                        code="FORBIDDEN_CHANGE_MENTION",
                        message=f"금지된 변경과 충돌할 수 있습니다: {rule}",
                        evidence_json={"forbidden_rule": rule},
                    )
                )

    moves = [block.rhetorical_move for block in blocks]
    recipe = context_pack.get("writing_recipe", {})
    if isinstance(recipe, dict):
        required_moves = [
            str(move).strip().upper()
            for move in recipe.get("required_moves", [])
            if str(move).strip()
        ]
        optional_moves = {
            str(move).strip().upper()
            for move in recipe.get("optional_moves", [])
            if str(move).strip()
        }
        allowed_moves = set(required_moves) | optional_moves
        normalized_moves = [str(move).strip().upper() for move in moves]
        cursor = 0
        missing_or_reordered: list[str] = []
        for required in required_moves:
            try:
                cursor = normalized_moves.index(required, cursor) + 1
            except ValueError:
                missing_or_reordered.append(required)
        unknown_moves = [move for move in normalized_moves if allowed_moves and move not in allowed_moves]
        if missing_or_reordered or unknown_moves:
            findings.append(
                AuditFinding(
                    project_id=document.project_id,
                    document_id=document.id,
                    audit_type="DISCOURSE",
                    severity="warning",
                    code="RECIPE_SEQUENCE_MISMATCH",
                    message="선택한 전개 방식의 필수 순서와 현재 문단 순서가 다릅니다.",
                    evidence_json={
                        "required_moves": required_moves,
                        "actual_moves": normalized_moves,
                        "missing_or_reordered": missing_or_reordered,
                        "unknown_moves": unknown_moves,
                        "audit_rules": list(recipe.get("audit_rules", [])),
                    },
                )
            )
    for move, count in Counter(moves).items():
        if count >= 4 and move in {"TURN", "INTERPRET", "ORIENT"}:
            findings.append(
                AuditFinding(
                    project_id=document.project_id,
                    document_id=document.id,
                    audit_type="DISCOURSE",
                    severity="warning",
                    code="REPEATED_RHETORICAL_MOVE",
                    message=f"{move} 수사 이동이 {count}회 반복됩니다.",
                    evidence_json={"move": move, "count": count},
                )
            )
    if blocks and not any(block.rhetorical_move in {"EXEMPLIFY", "ANCHOR"} for block in blocks):
        findings.append(
            AuditFinding(
                project_id=document.project_id,
                document_id=document.id,
                audit_type="DISCOURSE",
                severity="warning",
                code="NO_CONCRETE_ANCHOR",
                message="구체적 사례나 확정 사실을 담당하는 문단이 없습니다.",
            )
        )

    words = re.findall(r"[가-힣A-Za-z]{2,}", document.body_markdown)
    frequent = [(word, count) for word, count in Counter(words).most_common(10) if count >= 8]
    for word, count in frequent[:3]:
        findings.append(
            AuditFinding(
                project_id=document.project_id,
                document_id=document.id,
                audit_type="STYLE",
                severity="info",
                code="REPEATED_TERM",
                message=f"‘{word}’ 표현이 {count}회 반복됩니다.",
                evidence_json={"term": word, "count": count},
            )
        )

    for finding in findings:
        db.add(finding)
    db.commit()
    return findings
