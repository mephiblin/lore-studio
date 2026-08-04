from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import GenerationRun, GenerationStage, LoreBlock, LoreDocument, LoreRevision, PlaybookSession
from app.services.audits import run_audits
from app.services.config_loader import load_prompt
from app.services.context_compiler import compile_context
from app.services.model_gateway import ModelCallResult, ModelGateway

LENGTH_BUDGETS = {
    "short": 1200,
    "normal": 3000,
    "long": 6500,
    "very_long": 12000,
    "custom": 4000,
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
                ],
                "properties": {
                    "move": {"type": "string"},
                    "purpose": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "word_budget": {"type": "integer", "minimum": 50},
                    "must_include": {"type": "array", "items": {"type": "string"}},
                    "avoid": {"type": "array", "items": {"type": "string"}},
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


def _normalize_plan(data: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("structure_plan", data)
    if not isinstance(raw, dict):
        raise ValueError("Planner 출력의 최상위 구조가 올바르지 않습니다.")
    raw_blocks = raw.get("blocks", [])
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise ValueError("Planner 출력에 하나 이상의 blocks가 필요합니다.")
    target = LENGTH_BUDGETS.get(str(pack.get("generation_settings", {}).get("length", "normal")), 3000)
    selected_ids = [str(item.get("id")) for item in pack.get("selected_concepts", []) if item.get("id")]
    blocks: list[dict[str, Any]] = []
    for index, item in enumerate(raw_blocks, start=1):
        if not isinstance(item, dict):
            continue
        budget = item.get("word_budget")
        if not isinstance(budget, int):
            percentage = str(item.get("content_budget", "")).rstrip("%")
            try:
                budget = max(50, int(target * float(percentage) / 100))
            except ValueError:
                budget = max(50, target // len(raw_blocks))
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
                "locked": bool(item.get("locked", False)),
            }
        )
    if not blocks:
        raise ValueError("Planner 출력에서 유효한 block을 복구하지 못했습니다.")
    concept_role = raw.get("concept_role", {}) if isinstance(raw.get("concept_role"), dict) else {}
    title = raw.get("title") or concept_role.get("title")
    if not title:
        title = next((item.get("title") for item in pack.get("selected_concepts", [])), "새 로어")
    return {
        "title": str(title),
        "angle": str(raw.get("angle") or pack.get("user_direction") or "선택 자료의 의미를 단계적으로 드러낸다."),
        "blocks": blocks,
        "warnings": list(raw.get("warnings") or pack.get("warnings") or []),
        "planner_metadata": {
            key: raw[key]
            for key in ("concept_role", "conflict_resolution", "constraints_check")
            if key in raw
        },
    }


def _mock_plan(pack: dict[str, Any]) -> dict[str, Any]:
    recipe = pack.get("writing_recipe", {})
    moves = recipe.get("moves", [])
    move_map = {move.get("id"): move for move in moves if move.get("id")}
    ordered_ids = list(recipe.get("required_moves", []))
    optional = list(recipe.get("optional_moves", []))
    if optional:
        ordered_ids.insert(max(1, len(ordered_ids) - 1), optional[0])
    if "STING" in optional:
        ordered_ids.append("STING")

    settings = pack.get("generation_settings", {})
    target = LENGTH_BUDGETS.get(str(settings.get("length", "normal")), 3000)
    count = max(1, len(ordered_ids))
    titles = [item.get("title", "") for item in pack.get("selected_concepts", [])]
    subject = titles[0] if titles else "선택된 로어 대상"

    blocks = []
    for index, move_id in enumerate(ordered_ids, start=1):
        move = move_map.get(move_id, {})
        blocks.append(
            {
                "index": index,
                "move": move_id,
                "purpose": move.get("purpose", f"{move_id} 역할을 수행한다."),
                "evidence_ids": [item.get("id") for item in pack.get("selected_concepts", [])[:3]],
                "word_budget": max(120, target // count),
                "must_include": [],
                "avoid": ["작문 참고 자료의 고유 사실을 프로젝트 설정처럼 사용"],
            }
        )
    return {
        "title": subject,
        "angle": pack.get("user_direction") or f"{subject}의 성질과 세계관적 의미를 단계적으로 드러낸다.",
        "blocks": blocks,
        "warnings": pack.get("warnings", []),
    }


def _mock_draft(pack: dict[str, Any], plan: dict[str, Any]) -> str:
    concepts = pack.get("selected_concepts", [])
    title = plan.get("title") or (concepts[0].get("title") if concepts else "새 로어")
    summaries = [item.get("summary") or item.get("body") for item in concepts]
    summaries = [text.strip() for text in summaries if isinstance(text, str) and text.strip()]
    direction = pack.get("user_direction") or "선택된 설정의 의미를 서로 연결한다."

    paragraphs = [f"# {title}"]
    if summaries:
        paragraphs.append(
            "이 글은 현재 선택된 컨셉 페이지를 바탕으로 생성 흐름을 검증하기 위한 Mock 원고다. "
            + summaries[0][:260]
        )
    paragraphs.append(
        "플레이북은 자료를 한꺼번에 섞지 않고, 각 컨셉이 이번 글에서 맡은 역할을 분리한다. "
        f"이번 방향은 ‘{direction}’이며, 실제 모델 연결 시 선택한 집필 레시피의 문단 이동과 문체 규칙에 따라 확장된다."
    )
    for block in plan.get("blocks", [])[1:4]:
        paragraphs.append(
            f"[{block.get('move', 'BLOCK')}] {block.get('purpose', '')} "
            "이 문단은 Mock 모드이므로 완성 산문 대신 구성·저장·리비전 경계가 정상적으로 작동하는지 보여준다."
        )
    paragraphs.append(
        "여기서 새로 제안된 설정은 자동으로 세계관의 정사가 되지 않는다. 사용자가 원고를 검토하고 별도의 컨셉 페이지로 승인할 때에만 다음 창작의 확정 재료가 된다."
    )
    return "\n\n".join(paragraphs)


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


class LoreHarness:
    def __init__(self) -> None:
        self.gateway = ModelGateway()

    def context_preview(self, db: Session, session: PlaybookSession) -> dict[str, Any]:
        pack = compile_context(db, session)
        session.evidence_pack_json = pack
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

    async def plan(self, db: Session, session: PlaybookSession) -> dict[str, Any]:
        pack = compile_context(db, session)
        call_result: ModelCallResult | None = None
        if settings.mock_model:
            plan = _mock_plan(pack)
        else:
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
            model="mock" if settings.mock_model else str(call_result.model),
            endpoint="" if settings.mock_model else str(call_result.endpoint),
            runtime="mock" if settings.mock_model else "openai-compatible",
            prompt_components={
                "recipe": pack.get("writing_recipe", {}).get("key"),
                "recipe_version": pack.get("writing_recipe", {}).get("version"),
                "output_profile": session.output_profile,
            },
            selected_concept_ids=_selected_ids(session),
            direction_card_ids=session.direction_card_ids,
            params_json={
                **session.settings_json,
                "model_call": call_result.audit_metadata() if call_result else {},
            },
            input_hash=_stable_hash(pack),
            input_json=pack,
            usage_json={} if settings.mock_model else call_result.usage,
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

        call_result: ModelCallResult | None = None
        if settings.mock_model:
            body = _mock_draft(pack, plan)
        else:
            system_prompt = load_prompt("writer.md")
            payload = {
                "context_pack": pack,
                "article_plan": plan,
                "instruction": "완성된 한국어 본문만 출력하라.",
            }
            call_result = await self.gateway.complete(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
                ],
                role="writer",
                temperature=0.72,
                max_tokens=None,
                seed=session.seed,
            )
            body = call_result.content

        title = str(plan.get("title") or "새 로어 문서")
        paragraphs = _markdown_blocks(body)
        plan_blocks = list(plan.get("blocks", []))
        body_nodes: list[dict[str, Any]] = []
        for index, paragraph in enumerate(paragraphs):
            plan_block = plan_blocks[min(index, len(plan_blocks) - 1)] if plan_blocks else {}
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
        document = LoreDocument(
            project_id=session.project_id,
            session_id=session.id,
            writing_recipe_id=session.writing_recipe_id,
            title=title,
            body_markdown=body,
            body_json={"type": "doc", "content": body_nodes},
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
                author_type="llm" if not settings.mock_model else "mock",
            )
        )
        run = GenerationRun(
                project_id=session.project_id,
                session_id=session.id,
                document_id=document.id,
                task="draft",
                model_role="writer",
                model="mock" if settings.mock_model else str(call_result.model),
                endpoint="" if settings.mock_model else str(call_result.endpoint),
                runtime="mock" if settings.mock_model else "openai-compatible",
                prompt_components={
                    "recipe": pack.get("writing_recipe", {}).get("key"),
                    "recipe_version": pack.get("writing_recipe", {}).get("version"),
                    "output_profile": session.output_profile,
                },
                selected_concept_ids=_selected_ids(session),
                direction_card_ids=session.direction_card_ids,
                params_json={
                    **session.settings_json,
                    "model_call": call_result.audit_metadata() if call_result else {},
                },
                input_hash=_stable_hash({"pack": pack, "plan": plan}),
                input_json={"context_pack": pack, "article_plan": plan},
                usage_json={} if settings.mock_model else call_result.usage,
                output_text=body,
            )
        db.add(run)
        db.flush()
        for index, paragraph in enumerate(paragraphs):
            plan_block = plan_blocks[min(index, len(plan_blocks) - 1)] if plan_blocks else {}
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
            output_json={"document_id": document.id, "block_count": len(paragraphs)},
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
