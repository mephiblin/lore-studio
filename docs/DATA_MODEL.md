# 데이터 모델

현재 Alembic head는 `20260809_0005`입니다. `0001`이 PostgreSQL extension `vector`, schema `lore_app`/`lore_vector`, 기반 테이블을 만들고, `0002`~`0004`가 로어북 분리와 프로젝트 소유 자료 종류를 이관하며, `0005`가 버전형 문체 프로필·승인 예시·세션 선택 스냅샷을 추가합니다.

| 영역 | 테이블 | 핵심 경계 |
|---|---|---|
| 프로젝트 | projects, category_definitions | 최상위 namespace, 프로젝트 커버·사용자 설정, 프로젝트 소유 자료 종류 |
| 자료 | concept_pages, concept_page_revisions, concept_relations, attachments | 프로젝트 자료 종류 FK, 자유 Tiptap 본문, role/authority, era/continuity, facts/questions/forbidden |
| 지침/전개/표현 | direction_cards, direction_card_pools, writing_recipes, voice_profiles, voice_profile_examples | DirectionCard는 강조·금지, WritingRecipe는 정보 공개 순서, VoiceProfile은 문장 호흡·묘사·대화 원칙을 담당한다. 프로필은 상태·버전을 가지며 승인 예시는 권리 근거와 생성 사용 여부를 별도 보관한다. |
| 실행 | playbook_sessions, generation_runs, generation_stages | seed/선택/설정/plan/evidence와 모델 감사 |
| 문서 | lore_documents, lore_revisions, lore_blocks | `draft` 초안과 `lorebook` 완성본을 별도 행으로 저장, 출처 초안 ID·해시·최종 생성 설정, 위치/Move/근거/확실성/잠금, 전체 초안 원자 저장 리비전 |
| 검토 | audit_findings, proposed_concept_updates, reference_analyses, audit_logs | proposal/apply/dismiss 및 명시 승인 |
| 검색 | index_jobs, lore_vector.embedding_chunks | project/source/version/hash 격리 |

권위 전이는 `CANDIDATE → DRAFT_SETTING → PROJECT_CANON`만 허용합니다. 다른 source role은 근거 사용 정책이며 임의 승격 경로가 아닙니다. 후보 정사 승인은 내부적으로 두 단계를 모두 기록합니다.

프로젝트 커버는 `projects.settings_json.cover_image`/`cover_image_name`에 저장합니다. 클라이언트가 원본을 1200×675 JPEG로 정규화하고 API는 JPEG·PNG·WebP data URL과 2,500,000자 상한을 검증합니다. 생성 권위·네임스페이스와 무관한 표시 메타데이터이며 컨텍스트 컴파일에 포함하지 않습니다.

`category_definitions`는 반드시 `project_id`를 가지며 `(project_id, key)`가 유일합니다. `concept_pages(project_id, category_key)`는 이 복합 키를 참조하므로 다른 프로젝트의 종류를 지정할 수 없습니다. 종류 이름은 표시용이라 바꿀 수 있지만 key는 안정적으로 유지합니다. 사용 중인 종류 삭제는 API에서 차단하고, 사용하지 않는 종류의 명시 삭제는 감사 로그를 남깁니다. 기존 전역 종류는 각 프로젝트로 복사되고, `custom_category` 값은 프로젝트의 정식 자료 종류로 승격됩니다.

Embedding chunk 유일성은 project/source/version/chunk 단위이고 1024차원은 설정과 응답을 검사합니다. SQLite는 기본 단위/API test의 schema translation용일 뿐 운영 저장소가 아닙니다.

`voice_profiles.project_id=NULL`은 공용 범위, 값이 있으면 프로젝트 전용 범위입니다. 사용된 프로필의 수정은 기존 행을 덮지 않고 새 `DRAFT` 버전을 만들며, 세션과 `GenerationRun`은 실제 profile ID/version/example ID를 기록합니다. `ANALYSIS_ONLY` 예시와 비활성 예시는 Writer 입력에서 제외되고 모든 문체 예시는 `fact_eligible=false`입니다.
