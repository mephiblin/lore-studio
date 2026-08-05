# 아키텍처

```text
SvelteKit/Tiptap (5173, localhost)
  ├─ Concept Archive ─ 관계/권위/인덱스/Vision
  ├─ Playbook ─ seed/slots/cards/recipe/settings/plan/SSE progress
  └─ Lore Documents ─ LoreBlock/evidence/audit/Diff/candidate/export
                         │
FastAPI (18000, localhost)
  ├─ authority + revisions + audit logs
  ├─ context compiler + search + generation harness
  ├─ Canon / Discourse / Style audits
  └─ role-based model gateway
       ├─ Writer / Utility / Vision: host llama.cpp :8080
       └─ Embedding: host BGE-M3 llama.cpp :8010
                         │
PostgreSQL/pgvector (55432, localhost)
  ├─ lore_app: canonical app data and jobs
  └─ lore_vector: project-isolated embedding chunks
```

권위 원본은 PostgreSQL뿐입니다. 모델 출력은 후보/제안이며 DB 권위를 직접 바꾸지 못합니다. ConceptPage(자료), DirectionCard(이번 의도), WritingRecipe(전개 방식), output profile(형식), PlaybookSession(재현 가능한 조합)은 독립 객체입니다.

초안 Generation은 `COMPILE_CONTEXT → SELECT_ANGLE → PLAN → USER_EDITABLE_PLAN → DRAFT_BLOCKS → COHERENCE_PASS → CANON_AUDIT → DISCOURSE_AUDIT → STYLE_AUDIT → SAVE_REVISION`을 저장합니다. 사용자가 문단별 초안을 편집한 뒤 실행하는 완성 단계는 최신 LoreBlock 전체, 플레이북의 사용자 지시·레시피·출력 프로필·시점·시제·분량과 사실 경계를 다시 Writer에 전달하고 `FINAL_COHERENCE_PASS`를 별도 기록합니다. 초안과 완성본은 별도 필드와 revision으로 보존하며 초안 해시로 완성본의 오래된 상태를 판정합니다. 각 model call은 role/model/endpoint/runtime/sampling/usage/input hash를 기록하되 endpoint/key는 UI status에 노출하지 않습니다.

검색은 명시 선택을 우선 포함하고 lexical rank와 BGE-M3 cosine rank를 RRF로 합칩니다. factual role과 reference scope를 분리하며 embedding 장애는 FTS-only로 축소합니다.

DGX NVMe에는 DB/index/current models를, NAS에는 원본/장기 모델/backup을 두는 것을 권장합니다. Compose는 Lore Studio 전용 network/volume만 사용합니다.
