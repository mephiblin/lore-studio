# 데이터 모델

현재 Alembic head는 `20260808_0004`입니다. `0001`이 PostgreSQL extension `vector`, schema `lore_app`/`lore_vector`, 22개 테이블을 만들고, `0002`가 초안의 기존 완성 본문 필드를 추가했으며, `0003`이 이를 별도 로어북 문서 구조로 이관하고, `0004`가 자료 종류를 프로젝트 소유로 마이그레이션합니다.

| 영역 | 테이블 | 핵심 경계 |
|---|---|---|
| 프로젝트 | projects, category_definitions | 최상위 namespace, 프로젝트 커버·사용자 설정, 프로젝트 소유 자료 종류·추천 위치 |
| 자료 | concept_pages, concept_page_revisions, concept_relations, attachments | 프로젝트 자료 종류 FK, 자유 Tiptap 본문, role/authority, era/continuity, facts/questions/forbidden |
| 지침/전개 | direction_cards, direction_card_pools, writing_recipes, voice_profiles | DirectionCard는 프로젝트 집필 지침, WritingRecipe는 `project_id=NULL`인 공용 기본 방식과 프로젝트 소유 방식을 함께 지원하며 원문·parsed suggestion·version을 분리 |
| 실행 | playbook_sessions, generation_runs, generation_stages | seed/선택/설정/plan/evidence와 모델 감사 |
| 문서 | lore_documents, lore_revisions, lore_blocks | `draft` 초안과 `lorebook` 완성본을 별도 행으로 저장, 출처 초안 ID·해시·최종 생성 설정, 위치/Move/근거/확실성/잠금, 전체 초안 원자 저장 리비전 |
| 검토 | audit_findings, proposed_concept_updates, reference_analyses, audit_logs | proposal/apply/dismiss 및 명시 승인 |
| 검색 | index_jobs, lore_vector.embedding_chunks | project/source/version/hash 격리 |

권위 전이는 `CANDIDATE → DRAFT_SETTING → PROJECT_CANON`만 허용합니다. 다른 source role은 근거 사용 정책이며 임의 승격 경로가 아닙니다. 후보 정사 승인은 내부적으로 두 단계를 모두 기록합니다.

프로젝트 커버는 `projects.settings_json.cover_image`/`cover_image_name`에 저장합니다. 클라이언트가 원본을 1200×675 JPEG로 정규화하고 API는 JPEG·PNG·WebP data URL과 2,500,000자 상한을 검증합니다. 생성 권위·네임스페이스와 무관한 표시 메타데이터이며 컨텍스트 컴파일에 포함하지 않습니다.

`category_definitions`는 반드시 `project_id`를 가지며 `(project_id, key)`가 유일합니다. `concept_pages(project_id, category_key)`는 이 복합 키를 참조하므로 다른 프로젝트의 종류를 지정할 수 없습니다. 종류 이름은 표시용이라 바꿀 수 있지만 key는 안정적으로 유지합니다. 사용 중인 종류 삭제는 API에서 차단하고, 사용하지 않는 종류의 명시 삭제는 감사 로그를 남깁니다. 기존 전역 종류는 각 프로젝트로 복사되고, `custom_category` 값은 프로젝트의 정식 자료 종류로 승격됩니다.

Embedding chunk 유일성은 project/source/version/chunk 단위이고 1024차원은 설정과 응답을 검사합니다. SQLite는 기본 단위/API test의 schema translation용일 뿐 운영 저장소가 아닙니다.
