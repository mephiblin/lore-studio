# Recursive Product Audit

Overall status: ACTIVE

## Completion contract

- Primary user: DGX Spark에서 로컬 모델로 세계관을 축적하고 매일 로어를 집필하는 단일 사용자.
- Top job: 자료·방향·작문 방식·출력 설정을 통제 가능한 플레이북으로 조합해 근거가 추적되는 편집 가능한 로어를 실제 모델로 완성한다.
- In scope: 첨부 v1.0 요구사항의 DB, API, 모델, 검색, UI, 감사, 후보 승격, 멀티모달 최소 경로, 테스트, CI, 운영 문서.
- Non-goals: 외부 클라우드 LLM, 다중 사용자 인증, 저작권 원문/모델 파일 배포, 자동 정사 승격.
- Constraints: Ubuntu ARM64/DGX Spark, Docker Compose, PostgreSQL/pgvector, 로컬 OpenAI 호환 API, 프로젝트별 데이터 격리.
- Completion gates: 첨부 25개 완료 조건, 실제 Writer/Utility/Embedding 대표 흐름, 기본 오프라인 테스트, build/Compose/migration/E2E, 모든 FIX_NOW 검증.

## Product snapshot

- Repository / surface: `/home/inri/문서/lore-studio`, FastAPI + SvelteKit + Tiptap.
- Baseline revision or date: `facfc4f`, 2026-08-05.
- Runtime / test entry points: `docker compose`, `pytest`, `npm run build`, `/api/v1`, browser UI.
- Existing documentation: `README.md`, `TASKS.md`, `VERIFICATION.md`, `docs/*.md`, attached v1.0 completion contract.

## Current conclusion

설계 철학과 최소 Context→Plan→Draft 골격은 일관되지만 starter를 v1.0으로 신뢰할 수 없다. production frontend build, migration, role-based real-model routing, authority transitions, search/index isolation, daily-use editing flows and acceptance coverage are absent. Real Gemma Writer and BGE-M3 endpoints are available and have answered probe requests, so the implementation will target real integration rather than Mock as the completion proof.

## Cycle 1

### Audit findings

| ID | Severity | Domain | Finding | Evidence | Disposition | Acceptance criterion | Status |
|---|---|---|---|---|---|---|---|
| F-001 | P1 | Persistence | 런타임 create_all에 의존하며 Alembic, pgvector, lore_app/lore_vector 격리가 없다. | `backend/app/main.py`, no `alembic/`; baseline Compose inspection. | FIX_NOW | Fresh PostgreSQL migrates up/down/up and app uses isolated DB/schema/volume/network. | OPEN |
| F-002 | P1 | Models | 단일 모델 프로필이고 실제 role routing, health, capability, retry, streaming, structured output, fallback 기록이 없다. | Baseline `backend/app/services/model_gateway.py`; real endpoint probes. | FIX_NOW | Writer/Utility/Vision/Embedding health and representative real calls pass; used profile/model/params persist. | IMPLEMENTED |
| F-003 | P1 | Authority | 후보 상태와 승인 경계가 API/service invariant로 강제되지 않는다. | Models exist but router has no candidate transition endpoint or audit log. | FIX_NOW | Illegal direct canon transition fails; explicit audited candidate→draft→canon flow passes. | OPEN |
| F-004 | P1 | Retrieval | Project-isolated FTS/vector/RRF/reindex flow is absent. | No embedding model/service/table/API. | FIX_NOW | Selected pages always included; role/namespace filters and isolated BGE-M3 indexing/search pass. | OPEN |
| F-005 | P1 | Frontend | Production build fails and required editor/playbook/document flows are not usable. | `npm run build` fails on static env import; route source inspection. | FIX_NOW | Build and critical browser journeys pass with Korean errors, loading, persistence, and exports. | OPEN |
| F-006 | P1 | Generation | Required staged run, editable plan, LoreBlock metadata, rewrite Diff, three audits and candidate extraction are absent. | Harness implements only context→plan→draft. | FIX_NOW | Stage IO is persisted and representative plan/edit/draft/rewrite/audit/candidate/export flows pass. | OPEN |
| F-007 | P2 | Operations | Required commands, CI, backup/restore/security/model/evaluation docs are absent. | Makefile and docs inventory. | FIX_NOW | Requested commands and CI checks execute; operational docs match verified behavior. | OPEN |

### Research log

| Question | Conclusion | Sources | Inference / limits |
|---|---|---|---|
| Are real local models available? | Yes: Gemma 4 26B and Qwen3.5 4B are loaded behind llama.cpp router; BGE-M3 embedding server is listening. | Local `/v1/models`, process arguments, actual completion/embedding responses on 2026-08-05. | Utility JSON-mode compatibility is not yet established; first router request returned 500. |
| Should new model files be downloaded? | No. Required classes already exist locally; downloading would add risk and violate opt-in intent. | Local filesystem inventory and attached `ALLOW_MODEL_DOWNLOAD=false` requirement. | Qwen utility acceptance still requires evaluation. |
| Can starter status claims be trusted? | No. Current `VERIFICATION.md` describes a prior environment and frontend success is contradicted by today’s build failure. | Reproduced local commands above. | Results may change after implementation; report will be rewritten per cycle. |

### Decision and implementation

- Selected approach: establish real-model profiles first, then centralize persistence/authority/retrieval invariants, expose APIs, and build UI on stable contracts.
- Alternatives considered: keep SQLite/create_all for convenience (rejected for production and migration isolation); complete UI atop current skeleton (rejected because domain boundaries are not enforced); download requested named utility model (rejected because viable local candidates exist).
- Changes made: baseline execution, real endpoint discovery/probes, role-based Writer/Utility/Vision/Embedding profiles, model discovery/health/capabilities, retry, JSON object/schema requests, streaming, dimension-checked embeddings, Utility→Writer fallback, GenerationRun call metadata, frontend build fix, durable reports.
- Files / migrations / documentation: `backend/app/config.py`, `backend/app/services/model_gateway.py`, `backend/app/services/harness.py`, `backend/app/api/router.py`, model tests, `.env.example`, frontend API client, status documents.

### Verification

| Check | Command or method | Result | Artifact / evidence |
|---|---|---|---|
| Existing Python tests | `.venv/bin/pytest -q backend/tests` | PASS (3) | terminal output, implementation status. |
| Existing frontend build | `cd frontend && npm run build` | FAIL | Missing static public env export in `src/lib/api.js`. |
| Compose config | `make bootstrap && docker compose config --quiet` | PASS | Local `.env` created from ignored example. |
| Real Writer probe | POST `/v1/chat/completions` with Gemma 4 26B | PASS | Model ID and usage/timings returned. |
| Real Utility JSON probe | App gateway with Qwen3.5 4B direct profile | PASS | Parsed `{\"status\":\"ok\"}`; initial malformed curl probe was not a model defect. |
| Real BGE-M3 probe | POST `/v1/embeddings` | PASS | Non-empty embedding returned. |
| Role gateway units | `.venv/bin/pytest -q backend/tests/test_model_gateway.py ...` | PASS (5) | Retry/config/JSON and dimension boundary covered. |
| Real role integration | `RUN_LOCAL_MODEL_TESTS=true RUN_EMBEDDING_TESTS=true ... pytest backend/tests/test_local_models.py` | PASS (2) | Gemma Writer, Qwen Utility JSON, BGE-M3 1024-dimension. |
| Frontend production build | `cd frontend && npm run build` | PASS | adapter-node output generated. |

### Re-audit

- Regressions checked: no product code changed yet.
- New or changed findings: none.
- Remaining `FIX_NOW` items: F-001 through F-007.
- Recursion decision: CONTINUE

## Residual risks

| Risk | Impact | Mitigation / owner | Revisit trigger |
|---|---|---|---|
| Local model endpoints may differ between host and Compose networking. | Real integration unavailable inside container. | Configurable profiles, health UI, documented host binding; verify Compose path. | Integration phase. |
| Long real-model runs consume substantial unified memory/time. | Test instability or contention. | Small deterministic probes first; explicit opt-in full evaluations. | Evaluation phase. |

## Future capability backlog

| Priority | Capability | User value | Dependency | Revisit trigger | Current disposition |
|---|---|---|---|---|---|
| P3 | Multi-user auth and remote access hardening | Shared studio use | Stable single-user v1.0 | A second user/remote deployment is requested. | DEFER |
| P3 | Full graph/timeline canvas | Large-world visualization | Reliable relations/search | Daily-use text workflows are complete. | DEFER |

## Final completion checklist

- [ ] Completion contract passes.
- [ ] All `FIX_NOW` findings are `VERIFIED`.
- [ ] Required tests, builds, and critical journeys pass.
- [ ] Current conclusion and residual risks match the product.
- [ ] Future backlog is prioritized without expanding current scope.
- [ ] Final report validation passes.
