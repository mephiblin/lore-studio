#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = os.getenv("LORE_STUDIO_API", "http://localhost:18000/api/v1").rstrip("/")


def request(method: str, path: str, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {detail}") from exc


def text_doc(text: str) -> dict:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": paragraph}],
            }
            for paragraph in paragraphs
        ],
    }


def find_or_create_project():
    projects = request("GET", "/projects")
    existing = next((item for item in projects if item["slug"] == "black-route-demo"), None)
    if existing:
        return existing
    return request(
        "POST",
        "/projects",
        {
            "name": "검은 항로 데모",
            "slug": "black-route-demo",
            "description": "Lore Studio의 순환형 창작 흐름을 검증하는 원본 예시 세계관",
            "universe_namespace": "black-route",
            "settings_json": {"canon_policy": "user_approved_only"},
        },
    )


def find_or_create_page(project, payload):
    query = urllib.parse.urlencode({"project_id": project["id"]})
    pages = request("GET", f"/concept-pages?{query}")
    existing = next((item for item in pages if item["title"] == payload["title"]), None)
    if existing:
        return existing
    return request("POST", "/concept-pages", {"project_id": project["id"], **payload})


def find_or_create_card(project):
    query = urllib.parse.urlencode({"project_id": project["id"]})
    cards = request("GET", f"/direction-cards?{query}")
    title = "해결책이 사회적 의존으로 변한다"
    existing = next((item for item in cards if item["title"] == title), None)
    if existing:
        return existing
    return request(
        "POST",
        "/direction-cards",
        {
            "project_id": project["id"],
            "title": title,
            "body": "처음에는 항로 문제를 해결하지만, 시간이 지나며 식민지와 기관이 이를 포기할 수 없는 구조가 된다. 대가는 효능과 같은 메커니즘에서 발생한다.",
            "tags": ["의존", "사회", "비극"],
            "parsed_rules": {
                "must_include": ["초기 효능은 실제로 유용함", "폐쇄할 수 없는 이유"],
                "avoid": ["효능이 처음부터 거짓이었다는 반전"],
                "ending_preference": "문제가 새로운 질서로 정착함",
            },
            "weight": 1,
            "enabled": True,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true", help="Mock 또는 연결된 모델로 구성안과 원고까지 생성")
    args = parser.parse_args()

    project = find_or_create_project()
    lighthouse = find_or_create_page(
        project,
        {
            "title": "검은 등대",
            "category_key": "place",
            "tags": ["항해", "기억", "수도회", "주요설정"],
            "usage_role": "PROJECT_CANON",
            "status": "active",
            "namespace": "black-route",
            "summary": "북부 항로를 안정시키지만 통과자의 기억 일부를 소모하는 등대 시설.",
            "body_json": text_doc(
                "검은 등대는 북부 변경 식민지로 이어지는 항성항로의 유일한 안정점이다. 등대가 꺼지면 항로는 며칠 안에 관측 불가능한 난류로 무너진다.\n\n"
                "등대의 운용자들은 항해사가 잃은 기억이 단순히 소멸하지 않고 시설 내부 어딘가에 축적된다고 의심한다. 그러나 이를 확인하는 핵심 구획은 봉인되어 있다."
            ),
            "properties_json": {"current_state": "운용 중", "governing_power": "검은 등대 수도회"},
            "locked_facts": [
                "검은 등대는 북부 항로에 존재한다.",
                "등대는 항로를 안정시키는 대신 통과자의 기억 일부를 소모한다.",
                "북부 식민지는 등대가 없으면 보급을 유지할 수 없다.",
            ],
            "open_questions": ["소모된 기억은 어디에 남는가", "등대의 원래 제작자는 누구인가"],
        },
    )
    era = find_or_create_page(
        project,
        {
            "title": "제3 항해시대",
            "category_key": "event",
            "tags": ["시대", "항해", "식민"],
            "usage_role": "PROJECT_CANON",
            "status": "active",
            "namespace": "black-route",
            "summary": "장거리 항성항로가 식민지 정치와 경제를 재편한 시대.",
            "body_json": text_doc("제3 항해시대에는 항로를 소유한 기관이 행성의 군대보다 큰 정치적 영향력을 갖게 되었다."),
            "properties_json": {},
            "locked_facts": ["항로 기관은 식민지 생존에 직접적인 권력을 가진다."],
            "open_questions": [],
        },
    )
    order = find_or_create_page(
        project,
        {
            "title": "검은 등대 수도회",
            "category_key": "free",
            "tags": ["조직", "기억", "운용기관"],
            "usage_role": "DRAFT_SETTING",
            "status": "active",
            "namespace": "black-route",
            "summary": "등대를 관리하며 항해자의 기억 손실 기록을 독점하는 수도회.",
            "body_json": text_doc("수도회는 기억 손실을 항로 통과의 의학적 부작용으로 공식 분류한다. 내부 기록은 손실 양이 등대의 출력과 비례한다고 암시한다."),
            "properties_json": {},
            "locked_facts": [],
            "open_questions": ["수도회는 실제 원인을 얼마나 알고 있는가"],
        },
    )
    card = find_or_create_card(project)
    recipes = request("GET", "/writing-recipes")
    recipe = next((item for item in recipes if item["key"] == "progressive_exposition"), recipes[0])

    session = request(
        "POST",
        "/playbook-sessions",
        {
            "project_id": project["id"],
            "name": "검은 등대 설정 풀이",
            "concept_slots": {
                "subject": [lighthouse["id"]],
                "background": [era["id"]],
                "elements": [order["id"]],
                "conflicts": [],
                "wildcards": [],
            },
            "direction_card_ids": [card["id"]],
            "user_direction": "개인의 타락보다 사회 전체가 이 항로에 의존하게 되는 과정을 중심에 둔다.",
            "writing_recipe_id": recipe["id"],
            "output_profile": "lore_article",
            "settings_json": {
                "length": "long",
                "detail_level": 4,
                "context_depth": "wide",
                "creativity": "conservative",
            },
            "seed": 817261,
        },
    )

    print(f"Project: {project['name']} ({project['id']})")
    print(f"Playbook session: {session['id']}")
    if args.generate:
        plan = request("POST", f"/playbook-sessions/{session['id']}/plan", {})
        result = request("POST", f"/playbook-sessions/{session['id']}/generate", {})
        print("Plan blocks:", len((plan.get("plan") or {}).get("blocks", [])))
        print("Document:", result.get("document", {}).get("id"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI boundary converts failures to a nonzero exit
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
