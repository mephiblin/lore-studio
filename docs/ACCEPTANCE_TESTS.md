# v1.0 인수 결과

| # | 조건 | 결과 | 증거 |
|---:|---|---|---|
| 1 | Compose build/up | PASS | DB healthy, API 18000, UI 5173 |
| 2 | 프로젝트 생성 | PASS | 실제 API/UI 프로젝트 |
| 3 | 자유 본문 저장 | PASS | API integration + Tiptap UI |
| 4 | 카테고리/태그/역할/관계 검색 | PASS | page filters, related_to/relation_type, backlinks |
| 5 | 방향성 카드 다중 조합 | PASS | UI multi-select/conflict warning |
| 6 | 역할 선택/필터 풀 추첨 | PASS | 플레이북 4 소재 슬롯 |
| 7 | 고정/재추첨/seed 재현 | PASS | 결정론적 PRNG와 seed UI |
| 8 | 레시피/출력/길이/상세도/범위/자유도 | PASS | 플레이북 3·4단계 |
| 9 | 사실/질문/금지/참고 구분 | PASS | context preview 3패널 |
| 10 | editable plan | PASS | 실제 Gemma 5 blocks + 편집 UI |
| 11 | Gemma Writer 전체 원고 | PASS | 1,039자/5 blocks |
| 12 | 검증된 Utility | PASS | Gemma pass, Qwen reject |
| 13 | BGE-M3 검색 | PASS | 실제 Compose Dense hit |
| 14 | 임베딩 저장소 격리 | PASS | lore_studio_pgdata/lore_vector |
| 15 | LoreBlock 저장 | PASS | Tiptap custom node + DB rows |
| 16 | 부분 재작성 Diff 승인/취소 | PASS | real proposal/apply + dismiss API/UI |
| 17 | 근거와 감사 | PASS | evidence chip + 3 auditors |
| 18 | 자동 정사 금지 | PASS | invariant/API test |
| 19 | 후보 추출/승인 | PASS | real extraction/two-step audit |
| 20 | 참고 구조 분석·사실 격리 | PASS | raw body excluded + leakage tests |
| 21 | MD/HTML/JSON export | PASS | 실제 byte 결과 |
| 22 | 모델 서비스 미연결 UI E2E | PASS | 성공 응답 조작 없이 OFFLINE 상태와 반응형 UI 검증 |
| 23 | 실제 Writer/Utility/Embedding 결과 | PASS | `VERIFICATION.md`/evaluation JSON |
| 24 | migration/tests | PASS | PostgreSQL up/down/up, pytest/build/e2e |
| 25 | 상태 문서 일치 | PASS | README/TASKS/status/audit updated |

대표 실제 프로젝트 slug는 `black-route-chronicle`이며 로컬 전용 DB에 정식 컨셉 페이지 9개와 관계·방향성 카드를 보관합니다.
