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
- Baseline: `facfc4f` starter, 2026-08-05. Current audited revision: `65c44fb`, 2026-08-06.
- Runtime / test entry points: `docker compose`, `make test`, `make e2e`, `make test-models`, `/api/v1`, browser UI.
- Existing documentation: README, TASKS, VERIFICATION, acceptance, architecture/data/harness, local operation guides, UI information architecture, model evaluation JSON/Markdown.

## Current conclusion

Lore Studio는 starter가 아니라 실제 local-first v1.0으로 신뢰할 수 있다. 운영 DB는 Alembic과 전용 vector schema를 사용하고, 권위·reference·namespace 경계는 모델 판단이 아닌 서비스 코드와 테스트가 강제한다. 현재 Compose는 가상 생성 경로 없이 Gemma Writer/Utility/Vision과 BGE-M3로 대표 생성·검색·이미지·수정·후보·export를 완료했다. 초안은 전체 문단 단위로 저장되고 최신 초안은 별도 완성 단계를 거쳐 로어북 문서가 된다. 외부 TTS/ComfyUI가 없을 때는 명시된 fallback만 사용한다.

2026-08-06 후속 UX 재점검에서는 프로젝트 생성, 자료 선택 후 본문 이동, 설문형 글 만들기, 전개 방식/집필 지침 분리, 모바일 레이아웃, 초안 자동 저장, 별도 로어북, UI 용어 통합을 검증했습니다. 원고 수정이 단계 이동 시 저장되지 않던 문제는 전체 초안 원자 저장 API와 새로고침 회귀 테스트로 해소했습니다.

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
