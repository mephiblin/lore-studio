# 검증 기록

실행일: 2026-08-05, DGX Spark, 실제 로컬 모델 endpoint

## 자동 검증

- Ruff: `All checks passed`
- pytest: `10 passed, 3 skipped` (Writer/Utility, Embedding, Vision 실제 endpoint tests는 기본 suite에서 의도적으로 skip)
- 실제 모델 opt-in: `3 passed` (Writer/Utility structured output, BGE-M3 1024차원, Vision data URL)
- SvelteKit adapter-node production build: PASS
- Playwright Chromium desktop 1600×900/mobile 390×844: `10 passed`, 브라우저/API 오류와 가로 overflow 없음
- JSON Schema/YAML/Python bundle validation: PASS
- Docker Compose build/up: DB healthy, backend 18000, frontend 5173
- Alembic PostgreSQL: upgrade → downgrade → upgrade PASS; `lore_app` 21 tables, `lore_vector` 1 table

## 실제 모델/DB 인수

- `/models/status`: `mode=live`, Writer/Utility/Vision/Embedding 모두 available; endpoint/key 비노출
- Utility 합성 9건: Qwen3.5-4B FAIL(66.7%, namespace 누출), Gemma4-26B PASS(88.9%, namespace 격리 통과)
- BGE-M3: Compose backend에서 1024차원 1 page/1 chunk 재색인 COMPLETED, Dense 검색으로 `검은 등대` 반환, `dense_error=null`
- Vision: 실제 PNG data URL 분석, caption/objects/tags/uncertainties 반환, `persisted=false`
- Utility: 방향성 원문을 유지한 goals/sequence/must/avoid suggestion 반환
- Planner: 5개 evidence-assigned editable blocks 생성
- Writer: 1,039자, 5 LoreBlocks 문서 생성
- 단계: COMPILE_CONTEXT부터 SAVE_REVISION까지 10개 COMPLETED
- GenerationRun: Gemma Utility 3,164 tokens, Writer 3,756 tokens 및 model/runtime/input 기록
- 부분 재작성: 실제 Gemma proposal Diff 생성 후 APPLIED
- 후보: 2개 추출, 사용자 승인 후보는 CANDIDATE→DRAFT_SETTING→PROJECT_CANON 두 승격 로그 기록
- 참고 분석: 실제 Utility가 2개 rhetorical paragraph를 만들고 recipe/Voice Profile 후보를 사용자 승인으로 저장
- SSE: 실제 Writer 호출에서 progress와 complete event 및 저장 문서 반환
- export: Markdown 2,997 bytes, HTML 2,422 bytes, JSON 15,570 bytes

## 검증 경계

실제 외부 TTS와 ComfyUI job 제출은 설정되지 않아 문자 수 예상과 prompt 초안 fallback만 검증했습니다. `playwright-interactive`의 `js_repl`은 현재 세션에 없어, 같은 Playwright Chromium을 일반 runner로 실행해 기능/시각/viewport 검증을 대체했습니다.
