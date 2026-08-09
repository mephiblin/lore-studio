# 검증 기록

최신 갱신: 2026-08-09
기준 브랜치: `agent/project-taxonomy-and-ui-polish`
환경: DGX Spark, 실제 로컬 모델 endpoint

## 자동 검증

- Ruff: `All checks passed`
- pytest: `18 passed, 3 skipped` (Writer/Utility, Embedding, Vision 실제 endpoint tests는 기본 suite에서 의도적으로 skip)
- 실제 모델 opt-in: `3 passed` (Writer/Utility structured output, BGE-M3 1024차원, Vision data URL)
- SvelteKit adapter-node production build: PASS
- Playwright Chromium desktop 1600×900/mobile 390×844 실제 인수 자료 포함 회귀: `28 passed, 6 skipped`
- 프로젝트 전개 방식 생성·수정·글 만들기 선택·삭제 desktop/mobile 집중 회귀: `2 passed`
- 세계관 자료의 전개 방식 목록: 검은 항로/신규 프로젝트 모두 공용 기본 6개 노출, 프로젝트 전용 항목과 출처 구분 PASS
- 전개 방식·자료 종류 카드 갤러리: desktop 카드 폭 305px 이하, mobile 1열, 실제 `required_moves` 순서 표시, 별도 카드 표시·분류 기준 입력 제거, 단계 목적 자동 파생, 생성 후 폼 자동 접힘과 수정 접근 desktop/mobile PASS
- 새 세계관 자료 생성: 이름·자료 종류만 노출하고 `용도` 선택은 제거, API 기본값 `DRAFT_SETTING` 적용 desktop/mobile PASS
- 집필 지침 세부 규칙 직접 작성: 목표·전개 순서·반드시 포함·피할 전개·선호 결말의 API 저장·카드 표시 desktop/mobile `2 passed`
- 집필 지침 편집 작업면: 생성 폼·지침 목록·수정 폼이 데스크톱 독립 `overflow-y:auto` 영역을 공유하고, 생성·수정의 세부 규칙이 기본 펼침 상태임을 desktop/mobile `2 passed`; 자료 종류·집필 지침·전개 방식·글 만들기·원고 작업 도움말이 `position:fixed` 최상위 오버레이로 viewport 안에 표시됨을 전체 Playwright에서 확인
- 원고 작성 경계 AI 제안: 실제 Utility가 유지 사실 4·공개 유보 2·금지 변경 2개와 근거 구절을 반환, `persisted=false`; 선택 항목만 병합하고 사용자 저장 전 DB 미변경 PASS
- 세계관 자료 AI 본문 편집: 선택 범위 수정·전체/현재 위치/이어쓰기·연결 자료 기본 선택·실행별 참고 자료·CANDIDATE 비교/반영을 desktop/mobile `2 passed`; API는 DB 미변경·GenerationRun·교차 프로젝트 차단·참고 사실 격리 PASS
- AI 수정 문맥·확장 계약: 전체 본문과 선택부 앞뒤 전달, 문맥 요약·연결 조건 필수 응답, `더 자세히 (약 2배)` 최소 길이 JSON Schema와 4,200–8,000 출력 토큰 예산, GenerationRun 프롬프트 버전 기록 PASS. 실제 Gemma Writer에서 `기억세` 120자 선택부가 앞뒤 제도 맥락을 유지한 241자 제안으로 확장됐고 `persisted=false`, 저장 본문 120자 유지 PASS
- AI 수정·AI 작성 제안 본문: 진녹색 `#14322e` 배경과 아이덴티티 금색 `#f0bc65` 텍스트의 계산된 스타일을 desktop/mobile `2 passed`
- 모바일 전개 방식 화면 390×844: 문서/탭 가로 넘침 없음, 네 탭 `nowrap`, browser pageerror 없음 PASS
- 글 만들기·원고 작업 단계 메뉴의 `page-tools` 결합, 글 만들기 본문 외곽 여백 0, 자료 종류 추천 설정 제거를 1600×900/390×844/360×844에서 확인; 가로 넘침·pageerror 없음 PASS
- 73개 Diablo 자료에서 글 만들기 카드 18개 제한, 모바일 선택 영역 456px, 데스크톱 자료 목록 848px/내부 스크롤, `종족·생물` 필터, 단계 이동 pageerror 없음 PASS
- 모바일 프로젝트 생성 창 366×758(하단 메뉴 위), 프로젝트 제목 첫 화면 y=408, 로어북 읽기 기본/편집 왕복, 원고 도구 점프 PASS
- 원고 저장 회귀: 제목·문단 수정과 새 문단 추가 → 다음 단계 자동 저장 → 새로고침 복원 → 테스트 데이터 원상복구 PASS
- JSON Schema/YAML/Python bundle validation: PASS
- Docker Compose build/up: DB healthy, backend 18000, frontend 5173
- Alembic PostgreSQL head `20260805_0003`: upgrade → downgrade → upgrade PASS; `lore_app` 21 tables, `lore_vector` 1 table

## 2026-08-06 실행 상태

- `/api/v1/health`: `status=ok`
- `/api/v1/models/status`: `mode=live`; Writer/Utility/Vision/Embedding 모두 `available=true`
- Compose: DB healthy, backend `18000`, frontend `5173`
- UI 용어: `세계관 자료 / 집필 지침 / 전개 방식 / 결과물 형태 / 초안 / 완성본 / 로어북`으로 통일

## 2026-08-05 실제 모델/DB 인수

- `/models/status`: `mode=live`, Writer/Utility/Vision/Embedding 모두 available; endpoint/key 비노출
- Utility 합성 9건: Qwen3.5-4B FAIL(66.7%, namespace 누출), Gemma4-26B PASS(88.9%, namespace 격리 통과)
- BGE-M3: Compose backend에서 1024차원 1 page/1 chunk 재색인 COMPLETED, Dense 검색으로 `검은 등대` 반환, `dense_error=null`
- Vision: 실제 PNG data URL 분석, caption/objects/tags/uncertainties 반환, `persisted=false`
- Utility: 집필 지침 원문을 유지한 goals/sequence/must/avoid suggestion 반환
- Planner: 근거가 배정된 5문단 글의 흐름 생성
- Writer: 1,039자, 5 LoreBlocks 문서 생성
- 단계: COMPILE_CONTEXT부터 SAVE_REVISION까지 10개 COMPLETED
- GenerationRun: Gemma Utility 3,164 tokens, Writer 3,756 tokens 및 model/runtime/input 기록
- 부분 재작성: 실제 Gemma proposal Diff 생성 후 APPLIED
- 설정 후보: 2개 추출, 사용자 승인 후보는 CANDIDATE→DRAFT_SETTING→PROJECT_CANON 두 승격 로그 기록
- 참고 분석: 실제 Utility가 2개 rhetorical paragraph를 만들고 recipe/Voice Profile 후보를 사용자 승인으로 저장
- SSE: 실제 Writer 호출에서 progress와 complete event 및 저장 문서 반환
- export: Markdown 2,997 bytes, HTML 2,422 bytes, JSON 15,570 bytes

## 검증 경계

실제 외부 TTS와 ComfyUI job 제출은 설정되지 않아 문자 수 예상과 prompt 초안 fallback만 검증했습니다. `playwright-interactive`의 `js_repl`은 현재 세션에 없어, 같은 Playwright Chromium을 일반 runner로 실행해 기능/시각/viewport 검증을 대체했습니다.
