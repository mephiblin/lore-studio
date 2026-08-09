# Recursive Product Audit

Overall status: COMPLETE

## Completion contract

- Primary user: DGX Spark에서 로컬 모델로 세계관을 축적하고 매일 로어를 집필하는 단일 사용자.
- Top job: 세계관 자료·집필 지침·전개 방식·결과물 형태를 재현 가능한 글 만들기 기록으로 조합해 근거가 추적되는 초안과 완성본을 실제 모델로 만든다.
- In scope: 첨부 v1.0의 DB, API, 역할별 모델, 검색, UI, 감사, 후보 승격, 멀티모달 최소 경로, 테스트, CI, 운영 문서.
- Non-goals: 외부 cloud LLM, 다중 사용자 인증, 모델 파일 배포, 정식 설정 자동 승격, 실제 TTS/ComfyUI 서버 자체 제공.
- Constraints: Ubuntu ARM64/DGX Spark, Docker Compose, PostgreSQL/pgvector, 로컬 OpenAI-compatible API, 프로젝트 데이터 격리.
- Completion gates: 27개 인수 조건, 실제 Writer/Utility/Vision/Embedding 대표 실행, offline test/build/UI E2E, Compose/migration/browser, 모든 FIX_NOW 검증.

## Product snapshot

- Repository / surface: `/home/inri/문서/lore-studio`; FastAPI, SvelteKit, Tiptap, PostgreSQL, llama.cpp.
- Baseline: `facfc4f` starter, 2026-08-05. Current UI safety audit baseline: `a48864e`, 2026-08-09.
- Runtime / test entry points: `docker compose`, `make test`, `make e2e`, `make test-models`, `/api/v1`, browser UI.
- Existing documentation: README, TASKS, VERIFICATION, acceptance, architecture/data/harness, local operation guides, UI information architecture, model evaluation JSON/Markdown.

## Current conclusion

Lore Studio는 starter가 아니라 실제 local-first v1.0으로 신뢰할 수 있다. 운영 DB는 Alembic과 전용 vector schema를 사용하고, 권위·reference·namespace 경계는 모델 판단이 아닌 서비스 코드와 테스트가 강제한다. 현재 Compose는 가상 생성 경로 없이 Gemma Writer/Utility/Vision과 BGE-M3로 대표 생성·검색·이미지·수정·후보·export를 완료했다. 초안은 전체 문단 단위로 저장되고 최신 초안은 별도 완성 단계를 거쳐 로어북 문서가 된다. 외부 TTS/ComfyUI가 없을 때는 명시된 fallback만 사용한다.

2026-08-09에는 `CHANGE_SAFETY_CHECKLIST.md`와 `UI_PAGE_CONTRACT.md`를 기준으로 현재 다섯 페이지의 UI 안전성을 재감사했습니다. 글 만들기 하단 바의 과도한 수직 padding, 문체·필력 화면의 공통 설정 작업면 grid·스크롤 누락, 다량 설정 카드의 행 압축을 재현하고 수정했습니다. 실제 데이터 전체 E2E, 빈 데이터 E2E, desktop/mobile/narrow viewport, 100개 카드 stress 상태에서 모두 검증됐습니다.

## Cycle 1

### Audit findings

| ID | Severity | Domain | Finding | Evidence | Disposition | Acceptance criterion | Status |
|---|---|---|---|---|---|---|---|
| F-001 | P1 | Persistence | 운영 DB가 create_all에 의존하고 migration/vector 격리가 없었다. | PostgreSQL up/down/up; lore_app 21 tables와 lore_vector 1 table; dedicated volume/network. | FIX_NOW | Fresh PostgreSQL migration과 app startup이 통과한다. | VERIFIED |
| F-002 | P1 | Models | 단일 profile이고 role routing, capability, retry, structured output, streaming 기록이 없었다. | Actual status와 calls; SSE progress; GenerationRun model/usage; gateway tests. | FIX_NOW | Writer/Utility/Vision/Embedding 실제 호출과 audit가 통과한다. | VERIFIED |
| F-003 | P1 | Authority | 후보와 정사 승인 경계가 API invariant가 아니었다. | Illegal direct transition 409; candidate two-step promotion audit logs. | FIX_NOW | CANDIDATE에서만 명시 두 단계 승격이 가능하다. | VERIFIED |
| F-004 | P1 | Retrieval | project-isolated FTS/vector/reindex가 없었다. | Real BGE-M3 index job and Dense hit; leakage/filter tests. | FIX_NOW | 명시 선택, role/namespace 격리, isolated vector search가 통과한다. | VERIFIED |
| F-005 | P1 | Frontend | production build 실패와 핵심 편집 흐름 부재가 있었다. | Build PASS; Playwright desktop/mobile; reviewed screenshots; no overflow/errors. | FIX_NOW | 한국어 critical journey와 responsive build가 통과한다. | VERIFIED |
| F-006 | P1 | Generation | editable Plan, LoreBlock, Diff, audits, candidates, exports가 없었다. | Actual 5-block plan, 5 LoreBlocks, real Diff, candidates and three exports. | FIX_NOW | 단계 IO와 대표 plan/draft/rewrite/audit/candidate/export가 저장된다. | VERIFIED |
| F-007 | P2 | Operations | CI, backup/restore, model and security docs가 없었다. | Make targets, GitHub Actions, nine operation docs and guards. | FIX_NOW | 요청 명령과 CI config/bundle checks가 실행 가능하다. | VERIFIED |

### Research log

| Question | Conclusion | Sources | Inference / limits |
|---|---|---|---|
| 새 utility GGUF를 바로 받아야 하는가? | 아니다. 로컬 후보를 먼저 평가했고 Qwen은 안전 gate 실패, Gemma는 통과했다. | 로컬 9-case 결과; Hugging Face Qwen model card https://huggingface.co/FadedRedStar/Qwen3.5-4B-heretic-GGUF | E4B는 로컬에 없어 NOT RUN이며 다운로드는 계속 opt-in이다. |
| Vision에 무엇이 필요한가? | llama.cpp의 image input은 호환 model과 mmproj가 필요하고 alias를 discovery와 맞춰야 한다. | llama.cpp CLI README https://github.com/ggml-org/llama.cpp/blob/master/tools/cli/README.md | 현재 Gemma mmproj 조합은 실제 PNG 분석으로 검증했다. |
| GGUF와 mmproj 파일을 저장소가 관리해야 하는가? | 아니다. format/model artifact는 외부에 두고 정확한 파일과 hash만 운영자가 승인한다. | GGUF spec https://github.com/ggml-org/ggml/blob/master/docs/gguf.md; llama.cpp quantize README https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md | 다운로드 script는 resume, size, streaming SHA를 지원하지만 기본 차단된다. |

### Decision and implementation

- Selected approach: persistence/authority/search invariant를 서비스 경계에 먼저 두고 role gateway와 staged generation을 연결한 뒤 문서 중심 UI를 구축했다.
- Alternatives considered: SQLite 운영, 외부 vector DB 공유, Qwen 자동 fallback, 자동 canon 승격은 각각 migration, isolation, safety, authority 계약을 위반해 배제했다.
- Changes made: 22-table domain, Alembic, role gateway, hybrid search, 10-stage 초안 harness, LoreBlock/Diff/audits/candidates/reference/Vision/video fallback, 전체 초안 저장, `FINAL_COHERENCE_PASS`, 별도 로어북, responsive UI, tests/CI/ops.
- Files / migrations / documentation: `backend/app`, `backend/alembic`, `frontend/src`, `frontend/tests`, `scripts`, `.github/workflows/ci.yml`, README/TASKS/VERIFICATION와 `docs` 전체.

### Verification

| Check | Command or method | Result | Artifact / evidence |
|---|---|---|---|
| Python logic/API | `.venv/bin/pytest -q` | PASS; 13 passed, 3 opt-in skipped | authority, leakage, context, search, gateway, generation, draft persistence, API integration tests |
| Static/bundle | Ruff and `scripts/validate_bundle.py` | PASS | Python, JSON Schema, YAML |
| Frontend | `npm --prefix frontend run build` | PASS | adapter-node production output |
| Browser real data | `make e2e` | PASS; 18 passed, 2 skipped | desktop 1600x900, mobile 390x844, 360x844 overflow, draft save/reload |
| Model-offline UI | Compose with model endpoints unavailable | PASS | fabricated generation response 없이 OFFLINE 상태와 주요 UI 렌더링 |
| PostgreSQL migration | Alembic upgrade, downgrade, upgrade | PASS | vector extension and two schemas |
| Actual model stack | Compose status and representative API calls | PASS | live mode; Gemma and BGE available; endpoint/key hidden |
| Actual model opt-in tests | `make test-models` | PASS; 3 passed | Writer/Utility JSON, BGE-M3 dimension, Vision data URL |
| Actual creative loop | plan, generate, rewrite, candidate, reference, Vision, export, SSE | PASS | local DB runs and `VERIFICATION.md` metrics |
| Utility evaluation | two real local model candidates, 9 cases each | PASS decision | Qwen rejected; Gemma selected; committed JSON/Markdown |

### Re-audit

- Regressions checked: build, API startup/migration, authority invariant, reference fact exclusion, search filters, model-offline explicit failure, desktop/mobile viewport, 프로젝트 응답 경합, 전체 초안 저장과 curated data reload.
- New or changed findings: no remaining in-scope correctness finding. Static Playwright session tool was unavailable, so equivalent Chromium runner evidence and screenshots were reviewed.
- Remaining `FIX_NOW` items: none.
- Recursion decision: STOP_COMPLETE

## Cycle 2 — 페이지 UI 안전성

### Completion contract

- Primary user: 로컬에서 세계관 자료를 축적하고 초안과 로어북 글을 반복 작성하는 단일 사용자.
- Top job: 각 내부 페이지를 넓은 주 작업면으로 사용하면서 저장·취소·선택·생성·삭제 상태를 잃지 않고 다음 단계로 진행한다.
- In scope: 프로젝트, 세계관 자료의 다섯 탭, 글 만들기, 원고 작업, 로어북의 레이아웃·스크롤·고정 바·고아 UI·상태 복원과 관련 회귀 테스트.
- Non-goals: 신규 기능, 시각 브랜드 교체, 외부 모델·TTS·ComfyUI 기능 확장.
- Constraints: 기존 녹색·금색 시각 언어, project-first IA, desktop 1600×900, mobile 390×844와 360×844, 실제 사용자 데이터 보존.
- Completion gates: 아래 모든 `FIX_NOW`가 `VERIFIED`; 체크리스트 자동 검증과 실제 Chromium 핵심 경로 PASS; desktop/mobile clipping·가로 overflow·고정 바 중첩 없음; 최종 report validator PASS.

### Audit findings

| ID | Severity | Domain | Finding | Evidence | Disposition | Acceptance criterion | Status |
|---|---|---|---|---|---|---|---|
| F-008 | P3 | Playbook UI | `.playbook-navigation`이 40px 버튼에 상하 18px padding을 사용해 총 77px이며 작업면 높이를 불필요하게 차지한다. | Chromium 1600×900 computed style: `height=77`, `paddingTop=18`, `paddingBottom=18`, buttons `40/40`; `frontend/src/styles.css`. | FIX_NOW | 상하 padding을 10px 안팎으로 줄이고 버튼 접근성·desktop/mobile 고정 위치·겹침 검증을 통과한다. | VERIFIED |
| F-009 | P2 | Editor UI | 문체·필력만 공통 설정 manager selector에서 빠져 `display:block`, header/list 간격 0px, 콘텐츠 높이 220px이며 전체 높이·독립 스크롤을 쓰지 못한다. | Chromium 비교: 자료 종류·집필 지침·전개 방식 `display:grid`, gap 10px, height 812px; 문체·필력 `display:block`, gap 0px, height 220.1875px. `.voice-manager`가 desktop manager/scroll selector에서 누락됨. | FIX_NOW | 문체·필력이 다른 설정 탭과 같은 grid 10px 간격, 전체 작업면 높이와 `voice-profile-list` 독립 스크롤을 사용한다. | VERIFIED |
| F-010 | P2 | Editor density | 고정 높이 설정 gallery에 많은 카드가 들어오면 implicit grid row가 축소되어 카드 내용이 잘린 막대가 된다. | Chromium route interception으로 문체 프로필 100개 표시: list `752px`, `scrollHeight=752px`, 첫 카드 높이 약 17.6px; `/tmp/lore-audit-voice-dense-after.png`. 실제 DB 미변경. | FIX_NOW | 설정 gallery의 implicit row가 카드 content 높이를 보존하고, overflow는 list scroll로 처리되며 카드 폭·행 비겹침 검증을 통과한다. | VERIFIED |

### Research log

| Question | Conclusion | Sources | Inference / limits |
|---|---|---|---|
| 하단 바 전체 공통 padding을 줄여야 하는가? | 사용자가 지적한 대상은 글 만들기이며 원고 작업 footer는 저장 상태 문구도 수용한다. 공통 `.wizard-actions`를 바꾸지 않고 `.playbook-navigation`만 축소해야 회귀 범위가 작다. | 실제 computed style; `UI_PAGE_CONTRACT.md` 7·8절; `frontend/src/styles.css`. | 10px은 40px 버튼과 1px border를 합쳐 약 61px bar를 만드는 현재 token 기반 선택이다. |
| 문체·필력 빈 상태에 margin만 추가하면 충분한가? | 아니다. 0px 간격은 부모 manager가 공통 grid selector에서 빠진 증상이며, margin만 추가하면 실제 카드가 많을 때 독립 스크롤 누락은 남는다. `.voice-manager`와 `.voice-profile-list`를 공통 작업면 selector에 포함해야 한다. | 동일 viewport 네 탭 수치 비교; `frontend/src/styles.css` manager selectors. | 현재 프로젝트에 문체 프로필이 0개라 빈 상태를 직접 측정했고, 다량 목록은 CSS 구조와 회귀 fixture로 확인해야 한다. |
| 다량 카드 문제를 문체·필력에만 고칠 것인가? | 아니다. 자료 종류·전개 방식·문체·필력은 같은 제한 높이 gallery selector를 공유한다. `grid-auto-rows:max-content`를 공통 selector에 두어 콘텐츠 높이를 보존하고 list가 스크롤을 소유하게 해야 한다. | 100개 mocked profile 시각·수치 재현; 기존 `.wizard-card-grid`의 동일 회귀 방지 규칙; `UI_PAGE_CONTRACT.md` 6·11절. | 실제 운영 프로필은 현재 0개지만 사용자가 계속 추가할 수 있으므로 정상 수명주기에서 도달 가능한 상태다. |

### Decision and implementation

- Selected approach: 공통 작업면 규칙에 문체·필력을 편입하고, 글 만들기 전용 footer만 수직 밀도를 줄인다.
- Alternatives considered: 빈 상태에만 margin을 추가하는 방식은 목록 스크롤 결함을 남겨 배제했다. 모든 `.wizard-actions`를 줄이는 방식은 원고 작업 footer의 정보 밀도까지 바꿔 배제했다.
- Changes made: 글 만들기 전용 footer padding을 상하 10px로 축소했다. `.voice-manager`를 공통 설정 grid와 desktop full-height 작업면에 편입하고 `.voice-profile-list`가 독립 scroll을 소유하게 했다. 설정 gallery에 `grid-auto-rows:max-content`를 적용해 카드 높이를 보존했다.
- Files / migrations / documentation: `frontend/src/styles.css`, `frontend/tests/workspace.spec.js`, `VERIFICATION.md`, `docs/DEVELOPMENT.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/ACCEPTANCE_TESTS.md`, `docs/UI_PAGE_CONTRACT.md`, 이 감사 보고서.

### Verification

| Check | Command or method | Result | Artifact / evidence |
|---|---|---|---|
| Baseline spacing | Playwright Chromium computed style, 1600×900 | FAIL reproduced | `/tmp/lore-audit-editor-before.png`, 수치 로그 |
| Footer density | Chromium desktop/mobile computed style | PASS; 77px→61px, padding 18px→10px, button 40px 유지 | `/tmp/lore-audit-desktop-playbook-after.png` |
| Voice manager alignment | 네 설정 탭 computed style 비교 | PASS; grid, gap 10px, desktop height 812px, list overflow auto | `/tmp/lore-audit-desktop-voice-after.png` |
| Dense settings gallery | mocked API 100개, 실제 DB 미변경 | PASS; card 366.5px, list scrollHeight 9475px/clientHeight 752px, width 300px, 행 비겹침 | `/tmp/lore-audit-voice-dense-final.png`; dedicated E2E |
| 실제 데이터 UI E2E | `make e2e` | PASS; 31 passed, 7 intentional viewport skips | five routes, create/edit/cancel/delete, AI candidate, workflow, dense data |
| 빈 데이터 UI E2E | `npm --prefix frontend run test:e2e` | PASS; 19 passed, 19 data/viewport skips | offline-safe route and focused layout coverage |
| Python·DB | `make test`; `alembic current` | PASS; 23 passed, 3 opt-in model skips; `20260809_0006 (head)` | API, authority, deletion audit, persistence |
| Static·bundle·production | `make lint`; `make validate`; Svelte build; Compose rebuild/health | PASS | Ruff, schema/YAML, Docker config, adapter-node |
| Viewport·orphan controls | Chromium 1600×900, 390×844, 360×844 DOM/visual pass | PASS; horizontal overflow 0, page/console error 0, unnamed visible control 0, fixed bars non-overlap | `/tmp/lore-audit-{desktop,mobile,narrow}-*.png` |

### Re-audit

- Regressions checked: 다섯 route의 빈/실데이터, 프로젝트 접기, 세계관 자료 읽기·편집·AI 제안, 설정 modal, 글 만들기 선택·수정 복귀·고정 footer, 원고 저장, 로어북 읽기·편집·삭제, 100개 설정 카드, desktop/mobile/narrow overflow와 이름 없는 조작 요소.
- New or changed findings: F-010은 1차 수정 후 고밀도 재감사에서 발견해 같은 cycle에서 수정·검증했다. 이후 새 결함은 발견되지 않았다.
- Remaining `FIX_NOW` items: none.
- Recursion decision: STOP_COMPLETE

## Residual risks

| Risk | Impact | Mitigation / owner | Revisit trigger |
|---|---|---|---|
| Local model servers are host processes and not Compose-managed. | Reboot can leave roles unavailable. | Document exact start/health commands and expose per-role readiness. | DGX reboot or model alias change. |
| Gemma Utility missed one source-role semantic case. | Bad model suggestion could mislabel evidence. | Deterministic code owns source roles and promotions; suggestions never auto-apply. | A smaller candidate passes every gate. |
| No real TTS/ComfyUI endpoint was configured. | Timing and media job submission remain estimates/drafts. | Graceful character estimate and prompt fallback. | User configures those external services. |

## Future capability backlog

| Priority | Capability | User value | Dependency | Revisit trigger | Current disposition |
|---|---|---|---|---|---|
| P2 | Real TTS and ComfyUI adapters | Measured narration and direct media jobs | Stable external API credentials | User supplies endpoint contract. | DEFER |
| P3 | Cross-encoder reranker A/B | Better very-large-world retrieval | Representative corpus | Search quality regression is measured. | DEFER |
| P3 | Graph/timeline canvas | Large-world navigation | Mature relations | Text workflow becomes the bottleneck. | DEFER |
| P3 | Multi-user auth | Shared studio | Remote deployment hardening | A second user or network exposure is requested. | DEFER |

## Final completion checklist

- [x] Completion contract passes.
- [x] All `FIX_NOW` findings are `VERIFIED`.
- [x] Required tests, builds, and critical journeys pass.
- [x] Current conclusion and residual risks match the product.
- [x] Future backlog is prioritized without expanding current scope.
- [x] Final report validation passes.
