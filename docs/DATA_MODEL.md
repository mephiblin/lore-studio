# 데이터 모델

Alembic revision `20260805_0001`은 PostgreSQL extension `vector`, schema `lore_app`/`lore_vector`, 22개 테이블을 구성합니다.

| 영역 | 테이블 | 핵심 경계 |
|---|---|---|
| 프로젝트 | projects, category_definitions | 최상위 namespace와 사용자 template |
| 자료 | concept_pages, concept_page_revisions, concept_relations, attachments | 자유 Tiptap 본문, role/authority, era/continuity, facts/questions/forbidden |
| 지침/전개 | direction_cards, direction_card_pools, writing_recipes, voice_profiles | DirectionCard는 프로젝트 집필 지침, 기본 WritingRecipe는 프로젝트 독립 공유 전개 방식, 원문·parsed suggestion·version 분리 |
| 실행 | playbook_sessions, generation_runs, generation_stages | seed/선택/설정/plan/evidence와 모델 감사 |
| 문서 | lore_documents, lore_revisions, lore_blocks | `draft` 초안과 `lorebook` 완성본을 별도 행으로 저장, 출처 초안 ID·해시·최종 생성 설정, 위치/Move/근거/확실성/잠금 |
| 검토 | audit_findings, proposed_concept_updates, reference_analyses, audit_logs | proposal/apply/dismiss 및 명시 승인 |
| 검색 | index_jobs, lore_vector.embedding_chunks | project/source/version/hash 격리 |

권위 전이는 `CANDIDATE → DRAFT_SETTING → PROJECT_CANON`만 허용합니다. 다른 source role은 근거 사용 정책이며 임의 승격 경로가 아닙니다. 후보 정사 승인은 내부적으로 두 단계를 모두 기록합니다.

Embedding chunk 유일성은 project/source/version/chunk 단위이고 1024차원은 설정과 응답을 검사합니다. SQLite는 기본 단위/API test의 schema translation용일 뿐 운영 저장소가 아닙니다.
