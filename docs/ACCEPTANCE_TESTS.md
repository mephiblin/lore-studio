# v1.0 인수 결과

| # | 조건 | 결과 | 증거 |
|---:|---|---|---|
| 1 | Compose build/up | PASS | DB healthy, API 18000, UI 5173 |
| 2 | 프로젝트 생성 | PASS | 실제 API/UI 프로젝트 |
| 3 | 자유 본문 저장 | PASS | API integration + Tiptap UI |
| 4 | 프로젝트별 자료 종류/태그/역할/관계 검색 | PASS | 카드형 종류 생성·이름 수정·필터, 별도 분류 기준 제거, 다른 프로젝트 종류 연결 차단, 사용 중 삭제 차단, 이름 기반 연결/역연결 |
| 5 | 프로젝트 집필 지침 다중 조합 | PASS | 카드형 선택, 목적 설명, 충돌 경고 |
| 6 | 자료 역할 선택 | PASS | 한 단계에 한 역할만 노출, 전체 미배정 자료 18개·더 보기, 검색·종류 필터, 중복 역할 방지, 선택 단계 건너뛰기 |
| 7 | 선택/설정/seed 재현 | PASS | 생성 세션에 모든 선택과 seed 저장 |
| 8 | 공용·프로젝트 전개 방식/결과물/시점·시제/분량/범위/자유도 | PASS | 프로젝트 전개 방식 CRUD·격리, 실제 `required_moves` 카드 순서·자동 파생 단계 목적, 단계형 글 만들기와 요청 본문 E2E |
| 9 | 사실/질문/금지/참고 구분 | PASS | 쉬운 설명·툴팁을 포함한 ‘이 글이 참고할 세계관’ 3패널 |
| 10 | editable plan | PASS | 실제 Gemma 5 blocks + 압축형 ‘글의 흐름’ 편집 UI |
| 11 | Gemma Writer 전체 원고 | PASS | 1,039자/5 blocks |
| 12 | 검증된 Utility | PASS | Gemma pass, Qwen reject |
| 13 | BGE-M3 검색 | PASS | 실제 Compose Dense hit |
| 14 | 임베딩 저장소 격리 | PASS | lore_studio_pgdata/lore_vector |
| 15 | LoreBlock 저장 | PASS | 제목·상태·전체 문단 원자 저장, 문단 추가/수정/삭제, 단계 이동 자동 저장과 새로고침 복원, 모바일 편집 UI |
| 16 | 부분 재작성 Diff 승인/취소 | PASS | real proposal/apply + dismiss API/UI, 모바일 원고 도구 점프와 결과 자동 이동 |
| 17 | 근거와 감사 | PASS | UUID 대신 자료명 근거 chip + 3 auditors |
| 18 | 정식 설정 자동 승격 금지 | PASS | invariant/API test |
| 19 | 후보 추출/승인 | PASS | real extraction/two-step audit |
| 20 | 참고 구조 분석·사실 격리 | PASS | raw body excluded + leakage tests |
| 21 | MD/HTML/JSON export | PASS | 실제 byte 결과 |
| 22 | 모델 서비스 미연결 UI E2E | PASS | 성공 응답 조작 없이 OFFLINE 상태와 반응형 UI 검증 |
| 23 | 실제 Writer/Utility/Embedding 결과 | PASS | `VERIFICATION.md`/evaluation JSON |
| 24 | migration/tests | PASS | PostgreSQL up/down/up, pytest/build/e2e |
| 25 | 상태 문서 일치 | PASS | README/TASKS/status/audit updated |
| 26 | 초안 전체를 완성본으로 통합 | PASS | 완성 설정 전체 수정, `FINAL_COHERENCE_PASS`, 초안과 로어북 문서 분리, 출처 해시 변경 감지 |
| 27 | 로어북 독립 탐색 | PASS | 상단 로어북 메뉴, 기본 읽기/명시적 편집 모드, 줄바꿈 제목, 내보내기, 출처 초안 이동 |
| 28 | 세계관 자료 AI 본문 편집 | PASS | 선택 범위 문맥 수정, 실행별 참고 자료 선택, CANDIDATE 비교·반영, DB 자동 저장 금지, 교차 프로젝트·참고 사실 격리 |

대표 실제 프로젝트 slug는 `black-route-chronicle`이며 로컬 전용 DB에 정식 세계관 자료 9개와 관계·집필 지침을 보관합니다. 기본 전개 방식 프리셋은 공용이고, 사용자가 만든 전개 방식과 참고 분석 승인 결과는 프로젝트에 귀속됩니다. 최신 자동 검증 수치는 루트 `VERIFICATION.md`를 권위 기록으로 사용합니다.
