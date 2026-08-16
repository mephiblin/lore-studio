# 아키텍처

```text
SvelteKit/Tiptap (5173, trusted LAN)
  ├─ 세계관 자료 ─ 프로젝트 자료 종류/관계/권위/Vision
  ├─ 글 만들기 ─ seed/slots/guidance/recipe/voice/settings/plan/SSE progress
  ├─ 원고 작업 ─ LoreBlock/근거/audit/Diff/필력 점검/설정 후보/전체 초안 저장
  └─ 로어북 ─ 완성본/출처 초안 계보/export
                         │
FastAPI (18000, trusted LAN)
  ├─ authority + revisions + audit logs
  ├─ context compiler + generation harness
  ├─ Canon / Discourse / Style audits
  └─ role-based model gateway
       └─ Writer / Utility / Vision: OpenAI-compatible local models
                         │
PostgreSQL (55432, localhost)
  └─ lore_app: canonical app data
```

권위 원본은 PostgreSQL뿐입니다. 모델 출력은 후보/제안이며 DB 권위를 직접 바꾸지 못합니다. CategoryDefinition(프로젝트 자료 종류), ConceptPage(세계관 자료), DirectionCard(프로젝트 집필 지침), WritingRecipe(공용 기본 또는 프로젝트 소유 전개 방식), OutputProfile(결과물 형태), PlaybookSession(재현 가능한 조합)은 독립 객체입니다. CategoryDefinition과 프로젝트 WritingRecipe는 프로젝트 경계 안에 있고 ConceptPage와 PlaybookSession은 같은 프로젝트의 객체 또는 명시적인 공용 기본값만 참조합니다.

세계관 자료 본문 AI 편집은 `POST /concept-pages/{id}/ai/rewrite-selection`과 `POST /concept-pages/{id}/ai/draft`에서 수행합니다. 요청에는 저장 전 Tiptap 본문, 현재 작성 경계, 이번 실행에만 사용할 참고 자료 ID가 들어갑니다. 선택 영역 수정은 전체 본문 창과 선택부 앞뒤 문맥을 함께 전달하고, Writer가 문서 주제 요약과 연결 조건을 먼저 구조화한 뒤 대체문을 작성하게 합니다. `더 자세히`는 원문 길이에 따른 최소·목표 문자 수를 프롬프트와 응답 JSON Schema에 함께 기록하고 출력 예산을 확대합니다. 서버는 같은 프로젝트 자료만 허용하고 사실 가능 자료, 미확정 후보, 영감·문체 참고를 분리해 Writer 문맥을 구성합니다. 응답은 `persisted=false`, `status=CANDIDATE`, 기준 본문 해시를 가진 제안이며 ConceptPage를 수정하지 않습니다. 프론트는 기준 본문이 바뀐 제안을 적용하지 않고, 적용한 뒤에도 일반 `변경 저장` 전까지 로컬 편집 상태로 유지합니다. 모델·입력 문맥·참고 자료·출력은 `GenerationRun`에 기록합니다.

초안 Generation은 `COMPILE_CONTEXT → SELECT_ANGLE → PLAN → USER_EDITABLE_PLAN → DRAFT_BLOCKS → COHERENCE_PASS → CANON_AUDIT → DISCOURSE_AUDIT → STYLE_AUDIT → SAVE_REVISION`을 저장합니다. `COMPILE_CONTEXT`는 사용자가 누르는 별도 단계가 아니라 `PLAN` 요청 안에서 먼저 자동 실행됩니다. 서버는 선택한 목표 문자 수에 맞게 계획의 문단 예산 합계를 정규화합니다. 6,000자 이상은 OpenAI 호환 gateway 뒤의 모델 종류와 무관한 `block_segments` 전략으로 전개 블록을 여러 호출에 걸쳐 이어 쓰고 실제 문자 수 95% gate를 통과한 뒤에만 저장합니다. 사용자 편집은 `PATCH /documents/{id}/draft`에서 제목·상태·순서가 있는 LoreBlock 전체를 한 트랜잭션으로 저장하고, LoreDocument의 Markdown/JSON 스냅샷과 사용자 리비전을 함께 갱신합니다. 단계·프로젝트·초안을 바꾸기 전에는 프론트가 미저장 변경을 먼저 저장하며, 프로젝트 목록 요청은 마지막 요청만 화면에 반영합니다. 사용자가 문단별 초안을 편집한 뒤 실행하는 완성 단계는 최신 LoreBlock 전체를 `editable_draft`로, 최초 지시·전개 방식·결과물 형태·시점·시제·분량·사실 경계를 읽기 전용 원본 설계로 Writer에 전달합니다. 사용자는 `revision_brief`에서 보강 목표·강도·분량 방향만 선택하며 `FINAL_COHERENCE_PASS`가 이를 별도 기록합니다. `expand`가 장문 목표를 복구할 때도 같은 구간 전략과 길이 gate를 사용합니다. 완성 결과는 초안과 다른 `document_kind=lorebook` 문서로 저장하며, `source_document_id`와 초안 해시로 계보와 오래된 상태를 판정합니다. 원래 PlaybookSession은 수정하지 않고 실제 다듬기 선택은 로어북 문서와 GenerationRun에 기록합니다. 각 model call은 role/model/endpoint/runtime/sampling/usage/input hash를 기록하되 endpoint/key는 UI status에 노출하지 않습니다.

DGX NVMe에는 DB와 현재 모델을, NAS에는 원본·장기 모델·백업을 두는 것을 권장합니다. Compose는 Lore Studio 전용 network/volume만 사용합니다.

VoiceProfile은 승인·버전이 있는 표현 원칙이며 WritingRecipe·OutputProfile과 독립적으로 선택됩니다. Context compiler는 문체 규칙과 권리가 확인된 짧은 예시를 사실 근거와 다른 예산·권위로 전달합니다. 초안, Finalizer, 부분 재작성, 필력 점검은 같은 profile/version snapshot을 사용합니다.
