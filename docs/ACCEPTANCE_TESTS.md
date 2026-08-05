# v1.0 인수 결과

| # | 조건 | 결과 | 증거 |
|---:|---|---|---|
| 1 | Compose build/up | PASS | DB healthy, API 18000, UI 5173 |
| 2 | 프로젝트 생성 | PASS | 실제 API/UI 프로젝트 |
| 3 | 자유 본문 저장 | PASS | API integration + Tiptap UI |
| 4 | 카테고리/태그/역할/관계 검색 | PASS | 자료 필터, 이름 기반 연결/역연결, 관계 생성·삭제 |
| 5 | 글의 방향 규칙 다중 조합 | PASS | 카드형 선택, 목적 설명, 충돌 경고 |
| 6 | 자료 역할 선택 | PASS | 한 단계에 한 역할만 노출하는 설문형 흐름, 중복 역할 방지, 선택 단계 건너뛰기 |
| 7 | 선택/설정/seed 재현 | PASS | 생성 세션에 모든 선택과 seed 저장 |
| 8 | 집필 방식/결과물/시점·시제/분량/범위/자유도 | PASS | 단계형 글 만들기와 요청 본문 E2E |
| 9 | 사실/질문/금지/참고 구분 | PASS | context preview 3패널 |
| 10 | editable plan | PASS | 실제 Gemma 5 blocks + 편집 UI |
| 11 | Gemma Writer 전체 원고 | PASS | 1,039자/5 blocks |
| 12 | 검증된 Utility | PASS | Gemma pass, Qwen reject |
| 13 | BGE-M3 검색 | PASS | 실제 Compose Dense hit |
| 14 | 임베딩 저장소 격리 | PASS | lore_studio_pgdata/lore_vector |
| 15 | LoreBlock 저장 | PASS | Tiptap custom node + DB rows |
| 16 | 부분 재작성 Diff 승인/취소 | PASS | real proposal/apply + dismiss API/UI |
| 17 | 근거와 감사 | PASS | UUID 대신 자료명 근거 chip + 3 auditors |
| 18 | 자동 정사 금지 | PASS | invariant/API test |
| 19 | 후보 추출/승인 | PASS | real extraction/two-step audit |
| 20 | 참고 구조 분석·사실 격리 | PASS | raw body excluded + leakage tests |
| 21 | MD/HTML/JSON export | PASS | 실제 byte 결과 |
| 22 | 모델 서비스 미연결 UI E2E | PASS | 성공 응답 조작 없이 OFFLINE 상태와 반응형 UI 검증 |
| 23 | 실제 Writer/Utility/Embedding 결과 | PASS | `VERIFICATION.md`/evaluation JSON |
| 24 | migration/tests | PASS | PostgreSQL up/down/up, pytest/build/e2e |
| 25 | 상태 문서 일치 | PASS | README/TASKS/status/audit updated |

대표 실제 프로젝트 slug는 `black-route-chronicle`이며 로컬 전용 DB에 정식 컨셉 페이지 9개와 관계·방향성 카드를 보관합니다.
