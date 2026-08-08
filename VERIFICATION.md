# 검증 기록

최신 갱신: 2026-08-07
기준 커밋: `65c44fb` (`main`)
환경: DGX Spark, 실제 로컬 모델 endpoint

## 자동 검증

- Ruff: `All checks passed`
- pytest: `13 passed, 3 skipped` (Writer/Utility, Embedding, Vision 실제 endpoint tests는 기본 suite에서 의도적으로 skip)
- 실제 모델 opt-in: `3 passed` (Writer/Utility structured output, BGE-M3 1024차원, Vision data URL)
- SvelteKit adapter-node production build: PASS
- Playwright Chromium desktop 1600×900/mobile 390×844 실제 자료 회귀: `23 passed, 3 skipped`
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
