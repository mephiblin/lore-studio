from __future__ import annotations

import hashlib
import json
import random
import re
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import GenerationRun, LoreDocument, LoreRevision, PlaybookSession, WritingRecipe
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


class LoreHarness:
    def __init__(self) -> None:
        self.gateway = ModelGateway()

    def context_preview(self, db: Session, session: PlaybookSession) -> dict[str, Any]:
        pack = compile_context(db, session)
        session.evidence_pack_json = pack
        db.add(session)
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
                response_mode="json_object",
                max_tokens=5000,
                seed=session.seed,
            )
            plan = _json_from_text(call_result.content)

        session.plan_json = plan
        session.evidence_pack_json = pack
        session.state = "planned"
        db.add(session)
        run = GenerationRun(
            project_id=session.project_id,
            session_id=session.id,
            task="plan",
            model="mock" if settings.mock_model else str(call_result.model),
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
            output_text=json.dumps(plan, ensure_ascii=False),
        )
        db.add(run)
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
        document = LoreDocument(
            project_id=session.project_id,
            session_id=session.id,
            writing_recipe_id=session.writing_recipe_id,
            title=title,
            body_markdown=body,
            body_json={"type": "doc", "content": []},
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
        db.add(
            GenerationRun(
                project_id=session.project_id,
                session_id=session.id,
                document_id=document.id,
                task="draft",
                model="mock" if settings.mock_model else str(call_result.model),
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
                output_text=body,
            )
        )
        session.state = "generated"
        db.add(session)
        db.commit()
        db.refresh(document)
        return document
