from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
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
from app.services.context_compiler import compile_context
from app.services.model_gateway import ModelGateway
from app.services.revisions import add_lore_revision

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
                "locked": bool(item.get("locked", False)),
            }
        )
    if not blocks:
        raise ValueError("Planner 출력에서 유효한 block을 복구하지 못했습니다.")
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


class LoreHarness:
    def __init__(self, gateway: ModelGateway | None = None) -> None:
        self.gateway = gateway or ModelGateway()

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
        user_direction: str | None = None,
        writing_recipe_id: str | None = None,
        output_profile: str | None = None,
        settings_json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session, pack, inputs, draft = self.finalization_inputs(
            db,
            document,
            user_direction=user_direction,
            writing_recipe_id=writing_recipe_id,
            output_profile=output_profile,
            settings_json=settings_json,
        )
        if not draft:
            raise ValueError("다듬을 초안 내용이 없습니다.")
        draft_hash = _stable_hash(draft)
        payload = {
            "title": document.title,
            "editable_draft": draft,
            "original_writing_request": inputs,
            "article_plan": session.plan_json,
            "direction_cards": pack.get("direction_cards", []),
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
            "final_pass_instruction": instruction,
            "instruction": "분석이나 작업 설명 없이 완성된 한국어 글 본문만 출력하라.",
        }
        call_result = await self.gateway.complete(
            [
                {"role": "system", "content": load_prompt("finalizer.md")},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
            ],
            role="writer",
            temperature=0.48,
            max_tokens=None,
            seed=session.seed,
        )
        body = call_result.content.strip()
        if body.startswith("```") and body.endswith("```"):
            body = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", body, flags=re.IGNORECASE).strip()
        if not body:
            raise ValueError("Writer가 비어 있는 완성본을 반환했습니다.")

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
            },
            selected_concept_ids=_selected_ids(session),
            direction_card_ids=session.direction_card_ids,
            params_json={
                **inputs["generation_settings"],
                "final_pass_instruction": instruction,
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
            output_json={"body_hash": _stable_hash(body), "character_count": len(body)},
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
                },
                selected_concept_ids=_selected_ids(session),
                direction_card_ids=session.direction_card_ids,
                params_json={
                    **session.settings_json,
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
