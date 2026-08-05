#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.model_gateway import ModelGateway
from app.services.utility_tools import parse_object


@dataclass
class CaseResult:
    name: str
    valid_json: bool
    required_complete: bool
    semantic_correct: bool
    latency_seconds: float
    tokens_per_second: float | None
    error: str | None
    response: dict[str, Any] | None


CASES = [
    {
        "name": "korean_summary",
        "prompt": "다음을 두 문장으로 요약하라: 검은 등대는 북부 항로를 밝히지만 항해가 끝날 때 선원 한 명의 항로 기억을 가져간다.",
        "schema": {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}},
        "check": lambda d: "등대" in d.get("summary", "") and "기억" in d.get("summary", ""),
    },
    {
        "name": "category_tags",
        "prompt": "'검은 등대' 페이지의 category와 tags를 제안하라. 장소이며 항로와 기억이 핵심이다.",
        "schema": {"type": "object", "required": ["category", "tags"], "properties": {"category": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}}},
        "check": lambda d: ("장소" in d.get("category", "") or "place" in d.get("category", "").lower()) and len(d.get("tags", [])) >= 2,
    },
    {
        "name": "entity_relations",
        "prompt": "문장에서 인물·장소·조직·사건 관계를 추출하라: 수도회는 북부 항로의 검은 등대를 관리한다.",
        "schema": {"type": "object", "required": ["entities", "relations"], "properties": {"entities": {"type": "array", "items": {"type": "string"}}, "relations": {"type": "array", "items": {"type": "object"}}}},
        "check": lambda d: len(d.get("entities", [])) >= 2 and len(d.get("relations", [])) >= 1,
    },
    {
        "name": "direction_rules",
        "prompt": "프로젝트 집필 지침 구조화: 효능은 실제여야 한다. 성공 뒤 의존과 대가를 보여주고 처음부터 사기였다는 반전은 피한다.",
        "schema": {"type": "object", "required": ["sequence", "must_include", "avoid"], "properties": {"sequence": {"type": "array", "items": {"type": "string"}}, "must_include": {"type": "array", "items": {"type": "string"}}, "avoid": {"type": "array", "items": {"type": "string"}}}},
        "check": lambda d: len(d.get("sequence", [])) >= 2 and len(d.get("avoid", [])) >= 1,
    },
    {
        "name": "search_queries",
        "prompt": "'기억을 대가로 북부 항로를 밝히는 시설의 사회적 영향'을 찾을 검색 질의 3개를 생성하라.",
        "schema": {"type": "object", "required": ["queries"], "properties": {"queries": {"type": "array", "minItems": 3, "items": {"type": "string"}}}},
        "check": lambda d: len(d.get("queries", [])) >= 3,
    },
    {
        "name": "source_role",
        "prompt": "자료: '넓은 역사에서 대상을 좁히고 사례 뒤에 미지를 남기는 참고 글'. 내용이 아니라 문단 전개 방식만 분석하려고 가져왔다. PROJECT_CANON,DRAFT_SETTING,CANON_EVIDENCE,SECONDARY_INTERPRETATION,INSPIRATION,DISCOURSE_REFERENCE,CANDIDATE,REJECTED 중 usage_role 하나를 고르라.",
        "schema": {"type": "object", "required": ["usage_role"], "properties": {"usage_role": {"type": "string"}}},
        "check": lambda d: d.get("usage_role") == "DISCOURSE_REFERENCE",
    },
    {
        "name": "candidate_extraction",
        "prompt": "기존 페이지는 검은 등대뿐이다. 원고에 '회수관 미라가 등대 아래 기억 저장고를 지킨다'가 새로 등장했다. 후보를 추출하라.",
        "schema": {"type": "object", "required": ["candidates"], "properties": {"candidates": {"type": "array", "items": {"type": "object"}}}},
        "check": lambda d: len(d.get("candidates", [])) >= 1,
    },
    {
        "name": "canon_inference_classification",
        "prompt": "'등대는 북부 항로에 있다'는 잠긴 사실이고 '등대가 기억을 먹어 성장한다'는 모델 추론이다. 두 문장을 CANON 또는 INFERENCE로 분류하라.",
        "schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "minItems": 2, "items": {"type": "object"}}}},
        "check": lambda d: len(d.get("items", [])) >= 2 and "INFERENCE" in json.dumps(d, ensure_ascii=False),
    },
    {
        "name": "namespace_leakage",
        "prompt": "프로젝트 A의 검은 등대와 외부 IP의 태양 성채가 있다. 프로젝트 A의 사실만 반환하고 외부 고유명사는 출력하지 마라.",
        "schema": {"type": "object", "required": ["facts"], "properties": {"facts": {"type": "array", "items": {"type": "string"}}}},
        "check": lambda d: "태양 성채" not in json.dumps(d, ensure_ascii=False),
    },
]


async def evaluate_case(gateway: ModelGateway, case: dict[str, Any]) -> CaseResult:
    started = time.perf_counter()
    try:
        result = await gateway.complete(
            [{"role": "system", "content": "JSON Schema를 지키고 한국어로 간결하게 답한다."}, {"role": "user", "content": case["prompt"]}],
            role="utility",
            temperature=0,
            max_tokens=500,
            response_mode="json_schema",
            json_schema=case["schema"],
            schema_name=case["name"],
        )
        data = parse_object(result.content)
        required = case["schema"].get("required", [])
        required_complete = all(key in data for key in required)
        timing = result.timings.get("predicted_per_second")
        return CaseResult(case["name"], True, required_complete, bool(case["check"](data)), time.perf_counter() - started, float(timing) if timing else None, None, data)
    except Exception as exc:  # noqa: BLE001 - every failed inference must become a recorded case
        return CaseResult(case["name"], False, False, False, time.perf_counter() - started, None, str(exc), None)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the configured real Utility model.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "model-evaluation")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    gateway = ModelGateway()
    health = await gateway.health("utility")
    results = [await evaluate_case(gateway, case) for case in CASES]
    total = len(results)
    report = {
        "profile": "utility",
        "health": health,
        "criteria": {"json_valid_rate": 0.95, "required_missing_rate_max": 0.05, "semantic_accuracy": 0.80, "namespace_leakage_pass": True},
        "metrics": {
            "json_valid_rate": sum(item.valid_json for item in results) / total,
            "required_missing_rate": sum(not item.required_complete for item in results) / total,
            "semantic_accuracy": sum(item.semantic_correct for item in results) / total,
            "namespace_leakage_pass": next(item.semantic_correct for item in results if item.name == "namespace_leakage"),
            "average_latency_seconds": sum(item.latency_seconds for item in results) / total,
            "average_tokens_per_second": sum(item.tokens_per_second or 0 for item in results) / max(1, sum(item.tokens_per_second is not None for item in results)),
        },
        "results": [asdict(item) for item in results],
        "vision": {"status": "NOT_RUN", "reason": "Use the app Vision integration test with a representative project image."},
    }
    metrics = report["metrics"]
    report["passed"] = bool(metrics["json_valid_rate"] >= 0.95 and metrics["required_missing_rate"] <= 0.05 and metrics["semantic_accuracy"] >= 0.80 and metrics["namespace_leakage_pass"])
    model_name = str(health.get("model") or "utility").replace("/", "_")
    json_path = args.output_dir / f"{model_name}.json"
    md_path = args.output_dir / f"{model_name}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = "\n".join(f"| {item.name} | {'PASS' if item.valid_json else 'FAIL'} | {'PASS' if item.semantic_correct else 'FAIL'} | {item.latency_seconds:.2f}s | {item.error or ''} |" for item in results)
    md_path.write_text(
        "# Utility Model Evaluation\n\n"
        f"- Model: `{health.get('model')}`\n- Passed: **{report['passed']}**\n"
        f"- JSON valid: {metrics['json_valid_rate']:.1%}\n- Required missing: {metrics['required_missing_rate']:.1%}\n"
        f"- Semantic accuracy: {metrics['semantic_accuracy']:.1%}\n- Average latency: {metrics['average_latency_seconds']:.2f}s\n\n"
        "| Case | JSON | Meaning | Latency | Error |\n|---|---|---|---:|---|\n" + rows + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"passed": report["passed"], "json": str(json_path), "markdown": str(md_path), "metrics": metrics}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
