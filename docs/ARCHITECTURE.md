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

권위 원본은 PostgreSQL뿐입니다. 모델 출력은 후보/제안이며 DB 권위를 직접 바꾸지 못합니다. ConceptPage(자료), DirectionCard(프로젝트 집필 지침), WritingRecipe(프로젝트 독립 공유 전개 방식), output profile(형식), PlaybookSession(재현 가능한 조합)은 독립 객체입니다.

초안 Generation은 `COMPILE_CONTEXT → SELECT_ANGLE → PLAN → USER_EDITABLE_PLAN → DRAFT_BLOCKS → COHERENCE_PASS → CANON_AUDIT → DISCOURSE_AUDIT → STYLE_AUDIT → SAVE_REVISION`을 저장합니다. 사용자 편집은 `PATCH /documents/{id}/draft`에서 제목·상태·순서가 있는 LoreBlock 전체를 한 트랜잭션으로 저장하고, LoreDocument의 Markdown/JSON 스냅샷과 사용자 리비전을 함께 갱신합니다. 사용자가 문단별 초안을 편집한 뒤 실행하는 완성 단계는 최신 LoreBlock 전체와 사용자가 다시 확정한 지시·레시피·출력 프로필·시점·시제·분량·사실 경계를 Writer에 전달하고 `FINAL_COHERENCE_PASS`를 별도 기록합니다. 완성 결과는 초안과 다른 `document_kind=lorebook` 문서로 저장하며, `source_document_id`와 초안 해시로 계보와 오래된 상태를 판정합니다. 원래 PlaybookSession은 수정하지 않고 실제 완성 설정은 로어북 문서와 GenerationRun에 기록합니다. 각 model call은 role/model/endpoint/runtime/sampling/usage/input hash를 기록하되 endpoint/key는 UI status에 노출하지 않습니다.

검색은 명시 선택을 우선 포함하고 lexical rank와 BGE-M3 cosine rank를 RRF로 합칩니다. factual role과 reference scope를 분리하며 embedding 장애는 FTS-only로 축소합니다.

DGX NVMe에는 DB/index/current models를, NAS에는 원본/장기 모델/backup을 두는 것을 권장합니다. Compose는 Lore Studio 전용 network/volume만 사용합니다.
