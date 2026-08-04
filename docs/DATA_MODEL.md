# 도메인 데이터 모델

## Project

세계관 또는 작업 공간의 최상위 경계다.

주요 필드:

- `id`
- `name`
- `slug`
- `description`
- `universe_namespace`
- `settings_json`

## ConceptPage

자유 본문과 구조화 메타데이터를 함께 가진다.

- `category_key`
- `tags`
- `usage_role`
- `status`
- `namespace`
- `summary`
- `body_json`
- `properties_json`
- `locked_facts`
- `open_questions`

## ConceptRelation

페이지 간 의미 관계다.

```text
source_page ─ relation_type → target_page
```

## DirectionCard

사용자 원문과 선택적 구조화 해석을 저장한다.

- `body`
- `tags`
- `parsed_rules`
- `weight`

## WritingRecipe

작문 전략의 버전된 정의다.

- `key`
- `version`
- `recipe_json`
- `is_builtin`

## PlaybookSession

한 번의 생성 조합과 상태를 저장한다.

- 역할별 `concept_slots`
- `direction_card_ids`
- `user_direction`
- `writing_recipe_id`
- `settings_json`
- `seed`
- `plan_json`
- `evidence_pack_json`

## LoreDocument / LoreRevision

완성 또는 작업 중인 글과 리비전이다. 본문은 Markdown과 Tiptap JSON을 함께 둘 수 있다.

## GenerationRun

모델 호출의 감사 로그다.

## ProposedConceptUpdate

생성 원고에서 추출된 새 설정 후보다.

상태 흐름:

```text
PENDING → ACCEPTED_AS_DRAFT | ACCEPTED_AS_CANON | MERGED | REJECTED
```
