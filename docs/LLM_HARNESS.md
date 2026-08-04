# LLM 하네스 명세

## 1. 목표

자유로운 다중 에이전트 대화보다, 사용자가 중간 결과를 보고 수정할 수 있는 단계형 작업기를 구현한다.

```text
Brief
→ Context Compilation
→ Angle / Plan
→ Evidence Assignment
→ Draft
→ Canon Audit
→ Discourse Audit
→ Revision Proposal
→ User Commit
```

MVP는 `Context → Plan → Draft → Save`를 구현하고, 감사와 부분 수정은 확장한다.

## 2. 컨텍스트 팩

```json
{
  "project": {},
  "selected_concepts": [],
  "locked_facts": [],
  "summaries": [],
  "source_passages": [],
  "relations": [],
  "uncertainties": [],
  "open_questions": [],
  "forbidden_material": [],
  "direction_cards": [],
  "user_direction": "",
  "writing_recipe": {},
  "generation_settings": {}
}
```

컨텍스트 깊이에 따라 다음을 조절한다.

- `core`: 잠긴 사실과 요약만
- `balanced`: 직접 선택 페이지의 본문과 1단계 관계
- `wide`: 관련 페이지와 원문을 적극 포함
- `max`: 토큰 예산 내에서 검색 결과 확장

## 3. Planner 출력

Planner는 산문을 쓰지 않고 구체적인 Article Plan을 JSON으로 만든다.

```json
{
  "title": "작업 제목",
  "angle": "이번 글의 중심 해석",
  "blocks": [
    {
      "move": "ORIENT",
      "purpose": "독자를 시대적 맥락에 위치시킨다",
      "evidence_ids": ["concept:..."],
      "word_budget": 250,
      "must_include": [],
      "avoid": []
    }
  ]
}
```

## 4. Writer 입력

Writer는 다음만 받는다.

- 고정 역할·권위 규칙
- 컴파일된 컨텍스트 팩
- 승인된 Article Plan
- 집필 레시피
- 출력 프로필
- 분량·상세도·창작 자유도
- 현재 사용자 지시

Writer는 데이터베이스 변경 명령이나 메타데이터를 본문에 출력하지 않는다.

## 5. 창작 자유도 규칙

### Strict

- 기록된 사실만 사용
- 연결 문장도 보수적으로 작성
- 새 고유명사·수치·기관 금지

### Conservative

- 감각적 묘사와 작은 인과 연결 허용
- 프로젝트 핵심 사실 변경 금지

### Balanced

- 빈 공간에 새로운 사례·사건·세부 인물 허용
- 생성된 새 설정은 후보 상태

### Free

- 선택한 설정을 소재로 새로운 하위 설정을 적극 생성
- 그래도 네임스페이스와 사용 금지 설정은 지킨다.

## 6. GenerationRun 기록

모든 모델 호출에 다음을 남긴다.

```json
{
  "task": "plan|draft|audit|rewrite|extract",
  "model": "...",
  "runtime": "openai-compatible",
  "prompt_components": {
    "system": "...@version",
    "recipe": "...@version",
    "output_profile": "...@version"
  },
  "selected_concept_ids": [],
  "direction_card_ids": [],
  "seed": 0,
  "sampling": {},
  "input_hash": "...",
  "output": "..."
}
```

## 7. 실패 처리

- JSON 파싱 실패: 원문을 보존하고 한 번의 구조 복구 호출 또는 명시적 오류
- 컨텍스트 초과: 낮은 우선순위 원문부터 축약하고 사용자에게 누락 목록 표시
- 모델 서버 실패: 플레이북 세션과 구성 입력을 보존
- 감사 실패: 원고를 삭제하지 않고 감사 상태를 표시
- 서로 다른 네임스페이스 선택: 크로스오버 여부를 실행 전에 확인

## 8. Mock 모드

`MOCK_MODEL=true`에서는 모델 서버 없이도 프로젝트 생성, 컨텍스트 컴파일, 계획, 문서 저장 흐름을 시험할 수 있다. 실제 문체 품질을 평가하는 기능이 아니라 UI·데이터 흐름 검증용이다.
