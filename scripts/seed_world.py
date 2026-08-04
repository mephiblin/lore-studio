#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_BASE = os.getenv("LORE_STUDIO_API", "http://localhost:18000/api/v1").rstrip("/")
PROJECT_SLUG = "black-route-chronicle"
NAMESPACE = "black-route"


def request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {detail}") from exc


def text_doc(*paragraphs: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": paragraph.strip()}],
            }
            for paragraph in paragraphs
            if paragraph.strip()
        ],
    }


def upsert_project() -> dict[str, Any]:
    projects = request("GET", "/projects")
    payload = {
        "name": "검은 항로 연대기",
        "description": (
            "기억을 연료로 삼아 항성 항로를 유지하는 문명과, "
            "그 대가를 기록·독점하는 기관들의 정치를 다룬 스페이스 오페라 세계관."
        ),
        "universe_namespace": NAMESPACE,
        "settings_json": {
            "canon_policy": "user_approved_only",
            "genre": ["스페이스 오페라", "제도적 미스터리", "기억 공포"],
            "tone": "절제된 비극과 생활감 있는 제도 묘사",
        },
    }
    existing = next((item for item in projects if item["slug"] == PROJECT_SLUG), None)
    if existing:
        return request("PATCH", f"/projects/{existing['id']}", payload)
    return request("POST", "/projects", {"slug": PROJECT_SLUG, **payload})


def concept_pages() -> list[dict[str, Any]]:
    return [
        {
            "title": "검은 등대",
            "category_key": "place",
            "tags": ["항로", "기억", "거대구조물", "핵심설정"],
            "era": "제3 항해시대",
            "continuity": "본편",
            "summary": "통과자의 기억을 연료로 태워 북부 항로를 안정시키는 유일한 등대.",
            "body_json": text_doc(
                "검은 등대는 행성이 아니라 항로 중간의 중력 균열에 박힌 십이칠 키로미터 길이의 시설이다. 등대가 발사하는 검은 빛은 보이지 않지만, 선박의 항법장치는 그 리듬을 기준으로 난류 속에서 길을 계산한다.",
                "통과에는 대가가 필요하다. 항해자는 자신이 잃었다는 사실조차 알지 못하는 기억 하나를 내어준다. 대부분은 쾌쾌한 냄새나 오래된 노래처럼 작은 것이지만, 강한 난류를 건너면 사람의 이름과 약속, 자신이 어떤 사람이었는지에 대한 확신까지 사라진다.",
                "등대 외벽에는 설계자의 문자와 현재 문명의 수리 표식이 겹겹이 쌓여 있다. 핵심부를 이해하는 사람은 없고, 수도회는 그 무지를 의식과 규정으로 대체해 시설을 유지한다.",
            ),
            "properties_json": {
                "location": "북부 항로 중심 중력 균열",
                "operator": "검은 등대 수도회",
                "operational_state": "운용 중",
                "fuel": "통과자의 자전적 기억",
            },
            "locked_facts": [
                "검은 등대는 북부 항로의 유일한 안정점이다.",
                "등대는 통과자의 기억 일부를 소모한다.",
                "현재 문명은 등대의 핵심 작동 원리를 완전히 이해하지 못한다.",
            ],
            "open_questions": ["소모된 기억은 어디에 축적되는가?", "등대를 처음 건설한 종족은 누구인가?"],
            "forbidden_changes": ["기억 대가를 실은 없던 사기로 반전시키지 않는다."],
        },
        {
            "title": "백야항",
            "category_key": "place",
            "tags": ["항구", "식민지", "물류", "생활권"],
            "era": "제3 항해시대",
            "continuity": "본편",
            "summary": "검은 등대 항로에 전적으로 의존하는 북부 식민지의 유일한 공공 항구.",
            "body_json": text_doc(
                "백야항은 어두운 행성의 영구 황혼대에 자리한다. 항구 천장의 반사거울이 주거구에 인공 낮을 뿌리기 때문에, 시민들은 도시 전체를 항구와 같은 이름으로 부른다. 공기와 의약품, 종자, 핵심 부품의 칠할이 등대 항로를 통해 들어온다.",
                "시민의 신분증에는 항로 통과 횟수와 추정 기억 손실량이 기록된다. 일정 수치를 넘긴 노동자는 중요 직무에서 배제되지만, 그들 없이는 항구가 작동하지 않는다. 이 모순은 백야항 정치의 가장 깊은 균열이다.",
                "매년 정전기에는 수도회와 항만위원회가 보급 우선순위를 협상한다. 공식적으로는 생존 물자가 먼저지만, 실제로는 등대 보수 부품과 기억 기록지가 항상 첫 번째 선창을 차지한다.",
            ),
            "properties_json": {"population": 4200000, "government": "항만위원회", "supply_window_days": 19},
            "locked_facts": ["백야항은 등대 항로가 끊기면 19일 안에 핵심 물자가 고갈된다.", "시민 신분증에 기억 손실 추정치가 기록된다.", "항만위원회와 수도회는 서로의 권력을 필요로 한다."],
            "open_questions": ["공급망 다변화가 의도적으로 방해받았는가?", "기억 손실 등급은 누구의 이익을 위해 사용되는가?"],
            "forbidden_changes": ["백야항을 자급자족 가능한 도시로 바꾸지 않는다."],
        },
        {
            "title": "검은 등대 수도회",
            "category_key": "free",
            "custom_category": "조직",
            "tags": ["조직", "기록", "종교", "기술관료제"],
            "era": "제3 항해시대",
            "continuity": "본편",
            "summary": "등대를 의식·수리·행정의 결합으로 유지하며 모든 기억 손실 기록을 독점하는 기관.",
            "body_json": text_doc(
                "수도회의 성직자는 기도보다 수리 절차를 더 많이 외운다. 그들의 의식은 오래된 기계의 작동 순서를 번역하지 못한 채 보존한 것이다. 의식의 한 구절이 누락되면 등대 출력이 진짜로 흔들린다.",
                "수도회는 통과자의 선언 기억과 통과 후 검사를 비교해 손실 목록을 작성한다. 원본은 등대 내부의 회수실로 이송되고, 시민과 항만위원회에는 요약본만 제공된다. 정보의 비대칭은 수도회가 보유한 실질적 권력이다.",
                "입회자는 자신의 가장 소중한 기억을 문서로 써서 보관한 뒤, 그 기억이 언젠가 사라질 수 있음을 인정하는 서약을 한다. 그러나 상층부의 기록은 사라진 기억이 소멸하지 않는다는 가능성을 암시한다.",
            ),
            "properties_json": {"headquarters": "검은 등대 외환 수도원", "leader_title": "수석 기록자", "public_mandate": "항로 유지와 기억 손실 관리"},
            "locked_facts": ["수도회는 등대를 완전히 이해하지 못하지만 유지할 수는 있다.", "수도회는 통과자의 기억 손실 원본 기록을 독점한다.", "의식은 실제 기술 절차와 결부되어 있다."],
            "open_questions": ["상층부는 회수실의 기능을 얼마나 아는가?", "수도회 내부에 기록 공개를 원하는 파벌이 있는가?"],
            "forbidden_changes": ["수도회 전체를 단순한 악의 집단으로 묘사하지 않는다."],
        },
        {
            "title": "기억세",
            "category_key": "artifact",
            "tags": ["제도", "세금", "항해", "불평등"],
            "era": "제3 항해시대",
            "continuity": "본편",
            "summary": "항로 통과로 발생하는 기억 손실을 계량·보상·전가하는 법적 제도.",
            "body_json": text_doc(
                "기억세는 돈이 아니라 손실 가능성을 시민에게 배분하는 제도다. 수도회는 선박의 질량, 항로 위험도, 탑승자의 기존 손실 추정치를 계산해 항해 등급을 부여한다. 높은 등급일수록 더 많은 사람의 기억이 위험에 노출된다.",
                "자본이 있는 선주는 전문 기억 담보인을 고용하거나 보험에 가입한다. 반면 개인 항해자와 계약 노동자는 손실을 스스로 반복 부담한다. 사회는 이를 자원 분배라고 부르지만, 당사자들은 자신의 과거가 상류층의 물류비로 쓰인다고 말한다.",
                "보상 심사는 손실한 기억의 가치를 입증해야 한다는 모순을 가진다. 사라진 기억이 중요했다는 사실을 보여주려면, 손실 전에 남겨 둔 기록과 다른 사람의 증언에 의존해야 한다.",
            ),
            "properties_json": {"administrator": "기억손실 심사국", "unit": "회상 단위", "transferable": True},
            "locked_facts": ["기억세는 항로 이용의 실제 위험을 사회적으로 분배한다.", "기억 담보 계약은 합법이다.", "보상을 받으려면 손실한 기억의 가치를 간접 입증해야 한다."],
            "open_questions": ["자발적 기억 담보는 어디까지 자발적인가?", "보험사는 손실 예측 데이터를 어떻게 사용하는가?"],
            "forbidden_changes": ["기억세를 단순한 화폐 세금으로 바꾸지 않는다."],
        },
        {
            "title": "제3 항해시대",
            "category_key": "event",
            "tags": ["시대", "항해", "식민", "정치경제"],
            "era": "현재",
            "continuity": "본편",
            "summary": "안정 항로를 운영하는 기관이 행성 국가보다 큰 권력을 갖게 된 현재의 시대.",
            "body_json": text_doc(
                "제3 항해시대는 새로운 엔진의 발명이 아니라 고대 항로 시설의 재발견으로 시작되었다. 문명은 그 시설을 복제하지 못했지만 운영할 수는 있었고, 그 결과 항로를 발견한 기관이 영토를 소유한 국가보다 중요해졌다.",
                "식민지는 자치 헌장을 가지지만, 공기·식량·의약품이 지나는 항로를 스스로 통제하지 못한다. 군사적 독립은 가능해도 물류적 독립은 불가능하다. 이 시대의 정치는 주권보다 유지보수 일정표를 둘러싼 협상에 가깝다.",
                "기억 손실이 항로의 대가라는 사실은 공개되어 있다. 다만 손실이 어떻게 산정되고 어디로 가는지는 비공개다. 사람들은 비밀 자체보다 살아가기 위해 비밀을 묵인해야 하는 현실에 더 큰 분노를 느낀다.",
            ),
            "properties_json": {"start_event": "고대 안정 항로 시설 재발견", "political_unit": "항로 기관과 자치 식민지"},
            "locked_facts": ["제3 항해시대의 권력은 영토보다 항로 운영 능력에서 나온다.", "현재 문명은 고대 항로 시설을 복제하지 못한다.", "기억 손실 사실 자체는 공개 정보다."],
            "open_questions": ["두 번째 안정 항로를 독자 개발할 수 있는가?", "시설 재발견은 우연이었는가?"],
            "forbidden_changes": ["현재 문명이 검은 등대를 완전히 복제할 수 있게 하지 않는다."],
        },
        {
            "title": "레아 벨",
            "category_key": "person",
            "tags": ["인물", "항해사", "기억손실", "증언자"],
            "era": "제3 항해시대",
            "continuity": "본편",
            "summary": "자신이 잊은 인물의 존재를 항해 기록의 빈틈으로 추적하는 베테랑 도선사.",
            "body_json": text_doc(
                "레아 벨은 스물일곱 번 검은 등대를 통과한 도선사다. 그녀는 난류의 소리와 계기판의 미세한 반응만으로 항로 상태를 판단하며, 백야항에서 가장 험한 구간을 맡길 수 있는 사람으로 알려져 있다.",
                "그녀의 개인 기록에는 계속 같은 인물을 향한 메시지가 나오지만, 레아는 그 사람을 기억하지 못한다. 승무원 명부의 배열, 식량 사용량, 촬영된 손의 위치는 언젠가 다섯 번째 승무원이 있었음을 암시한다. 수도회 기록에는 해당 인물이 없다.",
                "레아는 수도회를 공개적으로 비난하지 않는다. 항로가 폐쇄되면 먼저 죽는 사람이 누군지 알기 때문이다. 대신 그녀는 모든 항해자에게 자신의 기억을 외부에 중복 기록하라고 권하며, 잃은 사람의 흔적을 공동체의 기록으로 복원하려 한다.",
            ),
            "properties_json": {"occupation": "도선사", "crossings": 27, "affiliation": "백야항 도선사 조합"},
            "locked_facts": ["레아는 검은 등대를 27회 통과했다.", "레아의 기록은 잃은 동료 한 명의 존재를 암시한다.", "레아는 항로 폐쇄를 원하지 않는다."],
            "open_questions": ["다섯 번째 승무원은 누구였는가?", "수도회 기록에서 그 인물을 삭제한 것은 누구인가?"],
            "forbidden_changes": ["레아가 잃은 기억을 간단히 되찾게 하지 않는다."],
        },
        {
            "title": "회수실",
            "category_key": "place",
            "tags": ["등대내부", "기록", "금지구역", "미스터리"],
            "era": "제3 항해시대",
            "continuity": "본편",
            "summary": "소모된 기억의 패턴이 물리적 현상으로 기록되는 등대 최심부의 봉인 구획.",
            "body_json": text_doc(
                "회수실은 등대 최심부의 자전과 수정 실린더로 채워진 구획이다. 항로가 열릴 때마다 실린더 표면에 미세한 신호가 새겨지며, 수도회는 그 무늬를 통과자의 손실 신고와 대조한다.",
                "수도회 공식 교리에서 회수실은 단지 출력 안정 장치다. 그러나 일부 기록자는 특정 실린더 근처에서 자신이 알지 못하는 노래를 떠올리거나, 타인의 추억으로만 가능한 꿈을 꾸었다고 증언한다.",
                "실은 삼중 봉인되어 있고 세 키는 수도회, 항만위원회, 도선사 조합이 하나씩 보관한다. 실을 열기 위해서는 세 기관의 동의가 모두 필요하지만, 최근 수도회 인장과 일치하지 않는 출입 흔적이 발견되었다.",
            ),
            "properties_json": {"access": "삼중 승인", "custodians": ["수도회", "항만위원회", "도선사 조합"], "official_function": "출력 안정"},
            "locked_facts": ["회수실의 실린더는 항로 운영 시 신호를 기록한다.", "실을 공식적으로 열려면 세 기관의 승인이 필요하다.", "최근 비인가 출입의 증거가 있다."],
            "open_questions": ["실린더에 기억 자체가 보존되는가?", "비인가 출입자는 어떤 키를 사용했는가?"],
            "forbidden_changes": ["회수실의 정체를 초기 설정에서 확정하지 않는다."],
        },
        {
            "title": "침묵 조약",
            "category_key": "event",
            "tags": ["조약", "정치", "기록통제", "사회적합의"],
            "era": "제3 항해시대 41년",
            "continuity": "본편",
            "summary": "기억 손실의 존재는 공개하되 개별 손실 원본은 수도회가 보관하도록 한 정치적 타협.",
            "body_json": text_doc(
                "침묵 조약은 기억 손실 증거를 완전히 은폐할 수 없게 된 뒤 체결되었다. 항만 노동자의 집단 증언과 도선사 조합의 항해 일지가 공개되자, 수도회는 손실 사실을 인정하는 대신 항로 운영의 자치권을 보장받았다.",
                "조약은 모든 통과자에게 사전·사후 기억 검사 권리를 부여한다. 동시에 개별 손실의 원본 기록을 시설 보안 정보로 분류해 수도회의 독점을 합법화했다. 시민은 자신이 무엇을 잃었는지 알 권리를 얻었지만, 왜 잃었는지 묻는 자료에는 접근할 수 없다.",
                "조약 명칭은 상대에게 비밀을 지키라는 뜻이 아니다. 생존을 위해 서로가 묻지 않을 범위를 정했다는 뜻이다. 그래서 조약은 압제의 상징이자 항로를 지킨 사회적 합의로 동시에 기억된다.",
            ),
            "properties_json": {"signatories": ["검은 등대 수도회", "백야항 항만위원회", "도선사 조합"], "year": 41, "status": "현행"},
            "locked_facts": ["침묵 조약은 기억 손실의 존재를 공식 인정했다.", "개별 손실 원본은 수도회가 독점 보관한다.", "조약은 현재도 효력이 있다."],
            "open_questions": ["조약 체결 직전 수도회가 폐기한 기록은 무엇인가?", "조약을 개정하면 항로 운영이 중단될 가능성이 있는가?"],
            "forbidden_changes": ["침묵 조약을 일방적 강요나 완전한 합의 한쪽으로만 단순화하지 않는다."],
        },
        {
            "title": "무명 해도",
            "category_key": "artifact",
            "tags": ["유물", "항법", "기억", "미확인항로"],
            "era": "제2 항해시대 말기",
            "continuity": "본편",
            "summary": "보는 사람이 잃은 기억에 따라 서로 다른 항로를 보여 주는 작성자 미상의 필사본.",
            "body_json": text_doc(
                "무명 해도는 백야항 문서고에서 발견된 여섯 장의 필사본이다. 같은 종이와 잉크로 작성되었지만, 관찰자마다 별의 위치와 항로 선을 다르게 기록한다. 사진에는 관찰자가 본 형상이 남아 객관적 비교가 가능하다.",
                "조사관들은 차이가 시력이나 심리 상태가 아니라 항로 통과 이력과 연관된다고 결론냈다. 특히 특정 인물을 잃은 사람들은 현재의 공식 항로와 겹치지 않는 짧은 경로를 본다. 그 경로의 끝에는 항상 검은 등대와 닮은 표식이 있다.",
                "수도회는 해도를 회수하지 않고 항만위원회와 공동 봉인했다. 정식 폐기를 요구하지 않은 이유는 공개되지 않았다. 레아 벨이 본 필사본에는 다섯 번째 승무원의 손글씨와 같은 주석이 나타난다.",
            ),
            "properties_json": {"copies": 6, "custody": "백야항 문서고 공동 봉인고", "author": "미상"},
            "locked_facts": ["무명 해도는 관찰자마다 다른 항로를 보여 준다.", "해도의 차이는 기억 손실 이력과 상관관계가 있다.", "레아의 필사본에는 잃은 승무원을 암시하는 주석이 보인다."],
            "open_questions": ["해도가 보여 주는 짧은 항로는 실재하는가?", "작성자는 기억 소모와 항로의 관계를 알았는가?"],
            "forbidden_changes": ["무명 해도의 모든 항로를 즉시 사실로 확정하지 않는다."],
        },
    ]


def upsert_pages(project: dict[str, Any]) -> dict[str, dict[str, Any]]:
    query = urllib.parse.urlencode({"project_id": project["id"]})
    existing = {item["title"]: item for item in request("GET", f"/concept-pages?{query}")}
    result: dict[str, dict[str, Any]] = {}
    for page in concept_pages():
        payload = {
            **page,
            "project_id": project["id"],
            "usage_role": "PROJECT_CANON",
            "status": "active",
            "namespace": NAMESPACE,
            "attachment_refs": [],
        }
        current = existing.get(page["title"])
        if current:
            update = {key: value for key, value in payload.items() if key != "project_id"}
            result[page["title"]] = request("PATCH", f"/concept-pages/{current['id']}", update)
        else:
            result[page["title"]] = request("POST", "/concept-pages", payload)
    return result


def ensure_relations(project: dict[str, Any], pages: dict[str, dict[str, Any]]) -> None:
    definitions = [
        ("검은 등대", "OPERATED_BY", "검은 등대 수도회", "수도회가 의식과 수리를 담당한다."),
        ("백야항", "DEPENDS_ON", "검은 등대", "항로가 끊기면 19일 안에 핵심 물자가 고갈된다."),
        ("기억세", "ADMINISTERED_BY", "검은 등대 수도회", "수도회의 손실 기록이 과세의 근거가 된다."),
        ("레아 벨", "INVESTIGATES", "무명 해도", "잃은 승무원의 흔적을 해도에서 찾는다."),
        ("무명 해도", "POINTS_TO", "회수실", "기억 소모와 대체 항로가 같은 원리를 공유할 가능성이 있다."),
        ("침묵 조약", "REGULATES", "회수실", "원본 기록 접근권을 세 기관에 분할한다."),
        ("제3 항해시대", "CONTEXT_FOR", "기억세", "항로 기관이 정치 권력을 갖는 제도적 배경이다."),
    ]
    known: set[tuple[str, str, str]] = set()
    for page in pages.values():
        for relation in request("GET", f"/concept-pages/{page['id']}/relations"):
            known.add((relation["source_page_id"], relation["relation_type"], relation["target_page_id"]))
    for source, relation_type, target, notes in definitions:
        key = (pages[source]["id"], relation_type, pages[target]["id"])
        if key not in known:
            request(
                "POST",
                "/concept-relations",
                {
                    "project_id": project["id"],
                    "source_page_id": key[0],
                    "relation_type": relation_type,
                    "target_page_id": key[2],
                    "notes": notes,
                },
            )


def ensure_direction_card(project: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode({"project_id": project["id"]})
    cards = request("GET", f"/direction-cards?{query}")
    payload = {
        "title": "유용한 제도가 사람을 소모한다",
        "body": "제도의 효능을 거짓으로 만들지 말고, 그 실제 효능 때문에 사회가 대가를 묵인하게 되는 과정을 보여 준다.",
        "tags": ["제도", "의존", "대가", "생존"],
        "compatible_tags": ["항로", "기억", "조직"],
        "incompatible_tags": ["단순음모"],
        "parsed_rules": {
            "must_include": ["제도의 실제 효능", "대체재가 없는 이유", "대가의 불균등한 분배"],
            "avoid": ["처음부터 모두가 알고 있던 악의", "기술 하나로 즉시 해결"],
            "ending_preference": "해결보다 선택의 비용을 남긴다",
        },
        "weight": 1.0,
        "priority": 10,
        "enabled": True,
    }
    current = next((item for item in cards if item["title"] == payload["title"]), None)
    if current:
        return request("PATCH", f"/direction-cards/{current['id']}", payload)
    return request("POST", "/direction-cards", {"project_id": project["id"], **payload})


def generate_document(project: dict[str, Any], pages: dict[str, dict[str, Any]], card: dict[str, Any]) -> None:
    recipes = request("GET", "/writing-recipes")
    recipe = next(item for item in recipes if item["key"] == "progressive_exposition")
    session = request(
        "POST",
        "/playbook-sessions",
        {
            "project_id": project["id"],
            "name": "기억으로 유지되는 항로",
            "concept_slots": {
                "subject": [pages["검은 등대"]["id"]],
                "background": [pages["제3 항해시대"]["id"], pages["백야항"]["id"]],
                "elements": [pages["기억세"]["id"], pages["검은 등대 수도회"]["id"]],
                "conflicts": [pages["레아 벨"]["id"]],
                "wildcards": [pages["무명 해도"]["id"]],
            },
            "direction_card_ids": [card["id"]],
            "user_direction": "등대의 비밀 폭로보다, 다른 대안이 없기 때문에 사회가 기억 소모를 제도화한 과정을 중심에 둔다.",
            "writing_recipe_id": recipe["id"],
            "output_profile": "lore_article",
            "settings_json": {"length": "long", "detail_level": 4, "context_depth": "wide", "creativity": "conservative"},
            "seed": 817261,
        },
    )
    plan = request("POST", f"/playbook-sessions/{session['id']}/plan", {})
    result = request("POST", f"/playbook-sessions/{session['id']}/generate", {})
    print(f"구성 문단: {len((plan.get('plan') or {}).get('blocks', []))}")
    print(f"생성 문서: {result.get('document', {}).get('id')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="검은 항로 연대기의 정식 세계관 자료를 적재합니다.")
    parser.add_argument("--generate", action="store_true", help="실제 연결 모델로 구성안과 원고까지 생성")
    args = parser.parse_args()

    project = upsert_project()
    pages = upsert_pages(project)
    ensure_relations(project, pages)
    card = ensure_direction_card(project)

    print(f"프로젝트: {project['name']} ({project['id']})")
    print(f"컨셉 페이지: {len(pages)}개")
    for title in pages:
        print(f"- {title}")
    if args.generate:
        generate_document(project, pages, card)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI boundary converts failures to a nonzero exit
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
