# 문체·필력(Voice Profile) 상세 구현 계획

구현 상태: **WP-0~WP-7 완료** (2026-08-09). WP-8 예시 임베딩 검색은 실제 사용 신호와 오염 방지 A/B 조건을 충족한 뒤 진행하는 후속 실험으로 유지한다.

- 상태: 구현 대기
- 작성일: 2026-08-09
- 대상 브랜치: `agent/project-taxonomy-and-ui-polish`
- 관련 도메인: `ConceptPage`, `ReferenceAnalysis`, `VoiceProfile`, `PlaybookSession`, `GenerationRun`

## 1. 결정 요약

Lore Studio에 사용자 화면 기준 `문체·필력`, 내부 도메인 기준 `VoiceProfile`을 독립 작문 자산으로 추가한다. 이 기능은 세계관 사실, 집필 지침, 전개 방식, 결과물 형태를 대체하거나 하나의 프롬프트 필드로 합치지 않는다.

첫 배포는 임베딩 검색 없이 다음 조합으로 구현한다.

1. 사용자가 직접 작성하거나 참고 글에서 승인한 문체 프로필 1개
2. 프로필에 속한 짧고 다양한 긍정 예시 3~5개
3. 원문 사실·고유명사 유입을 막는 결정론적 컨텍스트 분리
4. 생성 후 반복·상투성·예시문 복제를 찾는 필력 점검
5. 모든 프로필 버전·예시·모델 입력을 `GenerationRun`에 기록

일반 의미 임베딩은 문체 능력을 직접 높이지 않는다. 임베딩은 예시문 저장소가 커졌을 때 현재 장면에 맞는 예시를 고르는 보조 검색으로만 도입한다. 원문 소설 전체를 BGE-M3로 검색해 Writer에 자동 투입하는 구조는 범위에서 제외한다.

## 2. 정보 구조 원칙

### 2.1 IA 명제

사용자는 `세계관 자료` 영역에서 글에 재사용할 설정·지침·작문 자산을 객체별로 관리한다. `문체·필력`은 문장이 독자에게 어떻게 체감되는지를 정하는 독립 객체이며, 글 만들기에서는 전개 방식 다음에 선택해 현재 원고에 적용한다.

주 조직 원칙은 객체 중심이다. 전역 메뉴를 늘리지 않고 `세계관 자료`의 로컬 탭 안에 다섯 번째 객체 목록으로 추가한다.

```text
세계관 자료
├─ 세계관 자료      무엇이 사실인가
├─ 자료 종류        사실 자료를 어떻게 분류하는가
├─ 집필 지침        무엇을 강조하거나 피하는가
├─ 전개 방식        정보를 어떤 순서로 공개하는가
└─ 문체·필력        문장과 장면을 어떻게 체감시키는가
```

### 2.2 도메인 경계

| 객체 | 책임 | 포함하는 것 | 포함하지 않는 것 |
| --- | --- | --- | --- |
| `ConceptPage` | 세계관 내용 | 인물·장소·사건·규칙·자유 본문 | 재사용 문체 규칙 |
| `DirectionCard` | 집필 초점과 금지 | 강조점, 반드시 포함, 피할 전개 | 문단 공개 순서, 문장 리듬 |
| `WritingRecipe` | 정보 공개와 수사적 이동 | 필수 Move 순서, planner/audit 규칙 | 작가 목소리, 세계관 사실 |
| `VoiceProfile` | 표현 원칙 | 문장 호흡, 묘사, 대화, 비유, 문단 리듬 | 사실, 사건 순서, 결과물 종류 |
| `VoiceProfileExample` | 문체 시범 | 짧은 예시, 배울 점, 장면 태그 | 정식 설정, 자동 사실 근거 |
| `OutputProfile` | 결과 매체 | 설정 글, 영상 내레이션, 소설 장면, 세계 내부 문서·구술 | 프로젝트 문체 자산 |

### 2.3 용어 계약

| 위치 | 표시 이름 | 사용 규칙 |
| --- | --- | --- |
| 로컬 탭·페이지 제목 | `문체·필력` | 사용자가 찾는 장소 이름 |
| 카드 단위 | `문체 프로필` | 하나의 재사용 가능한 표현 규칙 묶음 |
| 원문 입력 | `예시 글` | 분석하거나 짧은 시범으로 사용할 글 |
| 생성 후 검사 | `필력 점검` | 자동 수정이 아닌 검토할 문제·수정 제안 |
| 내부 코드/API | `VoiceProfile` | 사용자 UI에 그대로 노출하지 않음 |

도움말 기본 문구는 다음으로 고정한다.

> 문장이 어떤 호흡과 밀도로 독자에게 전달될지 정합니다. 세계관 사실이나 전개 순서를 바꾸지 않습니다.

`작가 모사`, `스타일 복제`, `고급 문체` 같은 모호하거나 오해를 부르는 명칭은 기본 UI에서 사용하지 않는다.

## 3. 사용자 목표와 비목표

### 3.1 지원할 목표

- 사용자가 자신이 원하는 문장 감각을 재사용 가능한 자산으로 저장한다.
- 사용자가 직접 규칙을 작성하거나 예시 글에서 AI 분석 후보를 받는다.
- 분석 결과는 사용자가 승인한 항목만 문체 프로필로 저장한다.
- 글 만들기에서 문체 프로필 하나를 명시적으로 선택하거나 모델 기본 문체를 사용한다.
- 현재 원고에 실제 전달된 프로필·예시·버전을 최종 확인 화면에서 이해한다.
- 예시 글의 사실과 고유명사가 프로젝트 설정이나 생성 사실로 합류하지 않는다.
- 생성 결과가 예시 표현을 지나치게 복제하면 경고하고 수정 제안을 만든다.
- 프로필을 사용하지 않은 결과와 사용한 결과를 같은 입력·시드로 비교할 수 있다.

### 3.2 첫 구현의 비목표

- 특정 생존 작가 이름을 선택하는 작가 모사 카탈로그
- 소설 원문 전체를 자동 검색해 매 생성에 붙이는 RAG
- 여러 VoiceProfile을 가중치로 혼합하는 믹서
- 사용자별 LoRA·PEFT 학습
- 임베딩 벡터를 Writer 모델의 activation에 직접 주입하는 StyleVector
- 필력 점검 결과의 무승인 자동 덮어쓰기
- LLM 평가 점수 하나로 문학적 품질을 확정하는 기능

## 4. 현재 구현 상태와 실제 간극

### 4.1 이미 존재하는 기반

- `ConceptPage.usage_role=DISCOURSE_REFERENCE`: 참고 글을 사실 자료와 분리한다.
- `ReferenceAnalysis`: 문단 구조, 레시피 후보, voice 후보, 유사성 위험을 저장한다.
- `VoiceProfile`: 프로젝트 소유 프로필 JSON과 참고 분석 출처를 저장한다.
- `PlaybookSession.voice_profile_id`: 세션에 프로필 FK를 둘 수 있다.
- `RewriteRequest.voice_profile_id`: 부분 재작성 요청 필드는 이미 존재한다.
- `approve_reference_analysis`: 승인 시 WritingRecipe와 VoiceProfile을 함께 생성한다.
- `context_compiler`: `DISCOURSE_REFERENCE` 원문 본문을 제거하고 승인 분석만 비사실 자료로 다룬다.

### 4.2 연결되지 않은 부분

| 계층 | 현재 상태 | 필요한 변경 |
| --- | --- | --- |
| DB | `VoiceProfile`과 세션 FK 존재 | 버전·공용 범위·설명·예시 관계 추가 |
| Pydantic | 세션 Create/Read/Update에 voice ID 없음 | `voice_profile_id` 입출력 추가 |
| API | VoiceProfile CRUD/list 없음 | 범위 검증과 안전 삭제를 포함한 API 추가 |
| 참고 분석 | voice 후보를 빈 자유 JSON으로 허용 | 명시적 JSON Schema와 항목별 승인 구조 추가 |
| 프론트 | 분석 승인 뒤 전개 방식만 새로고침 | 문체 프로필 목록·상세·승인 결과 연결 |
| 글 만들기 | 프로필 선택 단계 없음 | 선택 단계·최종 표현 설계 카드 추가 |
| 컴파일러 | VoiceProfile을 조회하지 않음 | 프로필·승인 예시를 별도 pack으로 컴파일 |
| Writer | 문체 입력 계약 없음 | 구조화 태그·권위 규칙·예시 격리 추가 |
| Finalizer | 최초 생성의 문체 선택 재사용 없음 | 원본 프로필 버전과 변경 가능한 완성 설정 연결 |
| 부분 재작성 | `voice_profile_id` 요청 필드는 있으나 route가 사용하지 않음 | scope 검증, 프로필 로드, 앞뒤 문맥과 함께 Writer에 전달 |
| 감사 | 사실/Discourse/Style 감사 일부 존재 | 예시 복제·프로필 준수 결과와 사용자 판단 기록 |

현재 상태를 `참고 분석과 Voice Profile 후보 저장은 부분 구현, 원고 적용은 미구현`으로 취급한다.

## 5. 화면 및 사용자 흐름

### 5.1 문체·필력 목록

`세계관 자료` 로컬 명령줄에 다음 탭을 추가한다.

```text
세계관 자료 | 자료 종류 | 집필 지침 | 전개 방식 | 문체·필력
```

목록은 기존 프로젝트 카드 규격을 따른다. 대형 소개 패널은 두지 않고 제목 옆 `?` 도움말로 개념을 설명한다.

문체 프로필 카드에는 다음만 우선 표시한다.

- 프로필 이름
- 모든 프로젝트/현재 프로젝트 범위
- 한 줄 독서 인상
- 문장 호흡 요약
- 묘사·대화·비유 핵심 태그 최대 3개
- 승인 예시 수
- 출처: 직접 작성/예시 분석
- 수정, 복제, 삭제

카드 본문에 전체 규칙과 예시 원문을 펼치지 않는다. 카드는 탐색용이고 생성·수정은 모달 작업면에서 수행한다.

### 5.2 새 프로필 생성

`+ 새 문체 프로필`을 누르면 AI 작성과 같은 모달 작업면을 연다. 첫 화면에서 두 경로를 제시한다.

1. `직접 만들기`: 사용자가 규칙을 작성한다.
2. `예시 글에서 분석`: 사용자가 예시 글을 붙여넣거나 기존 예시 글을 선택한다.

두 경로는 같은 VoiceProfile로 귀결되지만 원문을 자동 승인하지 않는다.

직접 만들기 입력 필드는 다음 순서를 따른다.

1. 이름
2. 사용 범위: 모든 프로젝트/현재 프로젝트
3. 독자에게 남길 인상
4. 문장 호흡
5. 묘사와 감각
6. 대화와 서브텍스트
7. 비유와 어휘
8. 문단과 장면 전환
9. 피할 습관
10. 잘 맞는 장면
11. 완성 후 확인 기준

필수 입력은 이름과 독자에게 남길 인상뿐이다. 빈 구조 필드를 채우도록 강제하지 않는다.

### 5.3 예시 글 분석

`예시 글에서 분석`은 다음 순서로 진행한다.

```text
예시 글 입력 또는 선택
→ 사용 권한 확인
→ Utility가 구조·리듬·묘사·대화·위험 분석
→ 원문과 분석 후보를 나란히 검토
→ 사용할 항목만 선택
→ 문체 분석 CANDIDATE 생성
→ 사용자 승인 후 APPROVED 문체 프로필 생성
```

권한 선택지는 다음으로 제한한다.

- `직접 쓴 글`
- `사용 허가가 있는 글`
- `퍼블릭 도메인`
- `분석만 사용`

`분석만 사용`은 원문을 프로필 분석에만 쓰고 생성 예시로 직접 전달하지 않는다. 권한이 불명확한 기존 참고 자료는 마이그레이션 시 이 값으로 둔다.

분석 결과는 원문 고유명사나 긴 문장을 포함하지 않는다. 다음 항목별로 승인할 수 있어야 한다.

- 독서 인상
- 문장 길이 변화와 종결 경향
- 문단 밀도와 전환
- 서술 거리와 관찰 방식
- 감각 우선순위
- 대화·서브텍스트 방식
- 비유의 출처와 밀도
- 피할 만한 과적합·복제 위험

### 5.4 프로필 예시 관리

프로필 상세 모달 안에서 `짧은 예시`를 관리한다. 별도 상위 탭을 만들지 않는다.

예시 하나는 다음으로 구성한다.

- 표시 이름
- 1~3개 짧은 문단
- 이 예시에서 배울 점
- 장면 태그: 대화, 내면, 조사, 대치, 행동, 설명
- 권한 근거
- 생성 입력에 사용/분석에만 사용
- 활성 상태

긍정 예시를 중심으로 하며 반례는 최대 1개만 허용한다. 긴 금지 목록이 산문을 메마르게 만드는 것을 막기 위해 반례에는 `왜 피해야 하는지`를 반드시 함께 적는다.

### 5.5 글 만들기 선택 단계

`전개 방식`과 `결과물 형태` 사이에 선택 단계 하나를 추가한다.

```text
집필 지침 → 전개 방식 → 문체·필력 → 결과물 형태
```

- 선택은 선택 사항이다.
- `모델 기본 문체`를 명시적인 첫 카드로 제공한다.
- VoiceProfile은 한 번에 하나만 선택한다.
- 공용 프로필과 현재 프로젝트 프로필만 보여 준다.
- 다른 프로젝트 전용 프로필은 존재 자체를 노출하지 않는다.
- 카드에는 예시 원문이 아니라 프로필 요약과 잘 맞는 장면만 표시한다.

프로필 선택이 없으면 hidden default를 삽입하지 않는다. 생성 기록에는 `voice_profile_id=null`, `voice_selection_mode=model_default`를 남긴다.

### 5.6 최종 확인과 원고 작업

`확인·작성`의 `표현 설계` 카드에 다음을 함께 보여 준다.

- 결과물 종류
- 시점·시제
- 선택한 문체 프로필 또는 모델 기본 문체
- 사용될 짧은 예시 수
- 프로필 수정으로 돌아가기

전체 예시문과 내부 분석 JSON을 최종 확인 화면에 펼치지 않는다. `생성 입력 보기` 상세 영역에서만 실제 전달될 프로필과 예시 이름을 확인한다.

원고 작업에는 `필력 점검` 동작을 추가한다. 결과는 원고를 덮지 않고 문제 위치·이유·대체문을 가진 CANDIDATE 제안으로 표시한다. 기존 부분 재작성 승인/폐기 패턴을 재사용한다.

### 5.7 모바일·접근성 계약

- 다섯 로컬 탭은 390px에서 가로 페이지 overflow를 만들지 않는다.
- 라벨을 아이콘만으로 줄이지 않는다. 필요하면 균등 축소하거나 2행 명령줄을 사용한다.
- 프로필·예시 편집 모달은 본문만 스크롤하고 취소·저장 footer는 고정한다.
- 카드 선택은 색상뿐 아니라 `aria-pressed`, 체크 표시, 텍스트 상태를 함께 사용한다.
- 예시 분석 후보의 선택 상태와 승인 상태를 스크린 리더가 읽을 수 있게 한다.
- 글 만들기의 고정 `이전 / 계속` 바는 새 단계를 포함해 `.playbook-workspace` 밖에 유지한다.

## 6. 데이터 모델

### 6.1 VoiceProfile 확장

기존 `voice_profiles`를 다음 계약으로 확장한다.

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `id` | UUID/string | 기존 PK |
| `project_id` | nullable FK | `NULL`이면 모든 프로젝트, 값이 있으면 프로젝트 전용 |
| `key` | string | 버전 간 동일한 논리 식별자 |
| `version` | semver string | 생성 입력 재현용 |
| `name` | string | 사용자 표시 이름 |
| `description` | text | 한 줄 독서 인상 |
| `profile_json` | JSON | 구조화된 문체 규칙 |
| `source_analysis_id` | nullable FK/string | 참고 분석에서 생성된 경우 출처 |
| `is_builtin` | bool | 공용 읽기 전용 여부 |
| `status` | enum/string | DRAFT, APPROVED, DEPRECATED |
| `created_at/updated_at` | timestamp | 기존 규칙 |

PostgreSQL에서 `NULL`은 일반 unique 제약 안에서 서로 다른 값으로 취급되므로 고유성은 부분 index 두 개로 보장한다.

- 프로젝트 전용: `(project_id, key, version) WHERE project_id IS NOT NULL`
- 공용: `(key, version) WHERE project_id IS NULL`

사용된 프로필을 수정할 때 기존 row를 덮지 않고 새 버전을 만든다. 아직 어떤 세션에서도 사용하지 않은 DRAFT 프로필만 같은 버전 안에서 수정할 수 있다.

`project_id=NULL`인 사용자 공용 프로필은 로컬 단일 사용자 앱의 공용 자산으로 취급한다. 향후 다중 사용자 인증을 추가할 때 owner/workspace 경계를 별도 마이그레이션한다.

### 6.2 profile_json 계약

초기 JSON Schema는 자유 문자열과 얕은 배열을 사용한다. 빈 항목을 허용하되 알 수 없는 필드는 거부해 프롬프트 형태를 안정화한다.

```json
{
  "reader_effect": "절제된 문장 사이로 불안이 점차 커진다.",
  "sentence_rhythm": ["짧은 행동문과 긴 관찰문을 교차한다."],
  "description_rules": ["감정을 이름 붙이기보다 행동과 감각으로 드러낸다."],
  "dialogue_rules": ["대사의 내용과 행동의 어긋남으로 서브텍스트를 만든다."],
  "figurative_language": ["비유는 장면 안의 사물에서 가져온다."],
  "paragraph_rules": ["관련 행동과 관찰을 한 문단에 축적한다."],
  "avoid_patterns": ["감정을 설명한 뒤 다시 요약하지 않는다."],
  "best_for": ["대치", "조사", "내면"],
  "audit_rules": ["인물별 대사의 어휘와 회피 방식이 구분되는가"],
  "compatibility": {
    "viewpoints": ["third_limited"],
    "tenses": ["past"]
  }
}
```

`compatibility`는 추천 표시에만 사용하고 글 만들기의 시점·시제를 덮어쓰지 않는다.

### 6.3 VoiceProfileExample 신규 테이블

긴 예시를 `profile_json` 안에 넣지 않고 핵심 식별자와 상태를 정규화한다.

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `id` | UUID/string | PK |
| `voice_profile_id` | FK | 프로필 삭제 시 cascade |
| `source_concept_page_id` | nullable FK | 원문 참고 페이지가 있으면 연결 |
| `label` | string | 예시 이름 |
| `excerpt` | text | 생성에 전달 가능한 짧은 예시 |
| `teaches_json` | string array | 이 예시에서 배울 점 |
| `scene_tags` | string array | 대화/내면/조사/대치/행동/설명 |
| `rights_basis` | enum/string | SELF_AUTHORED, LICENSED, PUBLIC_DOMAIN, ANALYSIS_ONLY |
| `use_in_generation` | bool | ANALYSIS_ONLY이면 항상 false |
| `position` | int | 기본 노출·삽입 순서 |
| `status` | string | ACTIVE, DISABLED, REJECTED |
| `excerpt_hash` | string | 변경·복제 추적 |

예시는 `PROJECT_CANON`, `DRAFT_SETTING`, `CANON_EVIDENCE`로 승격할 수 없다. 설정 후보 추출 대상에서도 제외한다.

### 6.4 PlaybookSession·문서·GenerationRun

- 기존 `PlaybookSession.voice_profile_id`를 Create/Read/Update 스키마에 노출한다.
- `PlaybookSession.voice_selection_mode`를 `model_default`, `profile_default`, `manual`, `retrieved` enum/string 컬럼으로 추가한다.
- `PlaybookSession.voice_example_ids`를 예시 ID의 JSON 배열 컬럼으로 추가한다. 핵심 선택값을 범용 `settings_json` 안에 숨기지 않는다.
- 세션 생성 시 프로필이 APPROVED 상태이고 `project_id IN {NULL, session.project_id}`인지 검증한다.
- `voice_profile_id=NULL`이면 `voice_selection_mode=model_default`, `voice_example_ids=[]`만 허용한다.
- `LoreDocument.generation_inputs_json`에 프로필 ID·key·version·예시 ID·hash를 스냅샷으로 저장한다.
- `GenerationRun.input_json`에는 실제 컴파일된 프로필 JSON, 예시 ID, 예시 hash, token budget, 제외 사유를 기록한다.
- 예시 원문 전체는 GenerationRun에 중복 저장하지 않고 ID·hash와 실제 전달 excerpt만 기록한다.

## 7. API 계약

### 7.1 VoiceProfile CRUD

```text
GET    /voice-profiles?project_id={project_id}
GET    /voice-profiles/{profile_id}
POST   /voice-profiles
PATCH  /voice-profiles/{profile_id}
DELETE /voice-profiles/{profile_id}
POST   /voice-profiles/{profile_id}/duplicate
POST   /voice-profiles/{profile_id}/versions
POST   /voice-profiles/{profile_id}/approve
POST   /voice-profiles/{profile_id}/deprecate
```

목록은 공용(`project_id=NULL`)과 현재 프로젝트 소유 프로필만 반환한다. 공용 built-in은 수정·삭제하지 못한다. 다른 프로젝트 전용 프로필 조회는 404로 처리해 존재를 누출하지 않는다.

- 직접 만든 프로필은 DRAFT로 저장하며 `approve`는 명시적 사용자 동작이어야 한다.
- 사용 이력이 있는 프로필의 편집은 `versions`로 새 DRAFT 버전을 만들고, 재승인 전 생성에 사용하지 않는다.
- `deprecate`는 기존 세션·문서의 참조를 보존하면서 새 선택만 막는다.

삭제 규칙은 다음과 같다.

- 사용 이력이 없으면 삭제 가능
- PlaybookSession 또는 문서 생성 입력에서 사용했으면 `PROFILE_IN_USE` 409
- 사용 이력이 있으면 비활성화/새 버전 생성만 허용
- source reference는 프로필 삭제와 함께 삭제하지 않음

### 7.2 예시 CRUD

```text
GET    /voice-profiles/{profile_id}/examples
POST   /voice-profiles/{profile_id}/examples
PATCH  /voice-profile-examples/{example_id}
DELETE /voice-profile-examples/{example_id}
POST   /voice-profile-examples/{example_id}/toggle
```

API는 프로필 범위와 예시 source page의 프로젝트를 함께 검증한다. 공용 프로필에는 현재 프로젝트 전용 ConceptPage를 직접 예시 source로 연결하지 않는다. 공용 예시는 독립 excerpt 또는 공용 reference scope만 허용한다.

### 7.3 참고 분석

기존 endpoint를 유지하되 응답 Schema를 강화한다.

```text
POST /reference-analyzer/{page_id}
POST /reference-analyses/{analysis_id}/approve
```

`voice_candidate`는 자유 객체가 아니라 `profile_json`과 같은 구조를 반환한다. `similarity_risks`에는 원문 사실 유입 위험, 고유 비유 복제 위험, 단일 예시 과적합 위험을 구분한다.

승인 요청은 다음 선택값을 받는다.

```json
{
  "approve_recipe": true,
  "approve_voice_profile": true,
  "voice_scope": "PROJECT",
  "selected_voice_fields": ["reader_effect", "sentence_rhythm", "dialogue_rules"],
  "selected_example_ranges": []
}
```

전개 방식과 문체 프로필을 각각 승인할 수 있어야 한다. 현재처럼 한 번의 승인으로 둘을 무조건 함께 만드는 동작은 제거한다.

### 7.4 필력 점검

```text
POST /documents/{document_id}/prose-audit
POST /documents/{document_id}/prose-revision
```

- audit는 문제 위치와 이유만 반환한다.
- revision은 선택한 audit 항목에 대한 대체문을 CANDIDATE로 만든다.
- 두 요청 모두 저장된 최신 문서 hash와 voice profile version을 요구한다.
- 기준 문서가 바뀌면 기존 제안을 적용하지 않는다.
- 원고 자동 저장이나 설정 승격을 수행하지 않는다.

### 7.5 기존 생성 경로 확장

새 생성 endpoint를 별도로 복제하지 않고 기존 경로를 확장한다.

```text
POST /playbook-sessions/{session_id}/context-preview
POST /playbook-sessions/{session_id}/plan
POST /playbook-sessions/{session_id}/generate
POST /playbook-sessions/{session_id}/generate/stream
POST /documents/{document_id}/finalize
POST /blocks/{block_id}/rewrite
```

- context preview는 선택된 프로필 ID·version, 포함/제외 예시와 제외 이유를 보여 준다.
- plan은 문체가 전개 순서를 결정하지 못하게 하되 block의 `scene_mode`, `expression_focus`만 추천할 수 있다.
- generate와 stream은 동일 compiler 결과와 prompt version을 사용한다.
- `FinalizationRequest`의 기존 `voice_profile_id`, `voice_selection_mode`, `voice_example_ids` override는 API 호환성을 위해 남기되, 기본 원고 작업 UI는 이를 보내지 않고 초안의 generation snapshot을 상속한다. 완성 다듬기에서는 문체를 다시 선택하지 않는다.
- 기존 `RewriteRequest.voice_profile_id`는 실제로 검증·로드한다. 보내지 않으면 문서 snapshot을 상속하며, 선택된 문단 앞뒤 문맥과 프로필 version을 함께 전달한다.
- 모든 override는 현재 문서의 project scope와 APPROVED 상태를 다시 검증하고 `GenerationRun`에 원본 선택과 override를 모두 기록한다.

## 8. 컨텍스트 컴파일 계약

### 8.1 컴파일 결과

`compile_context`는 VoiceProfile을 별도 필드로 포함한다.

```json
{
  "selected_concepts": [],
  "direction_cards": [],
  "writing_recipe": {},
  "voice_profile": {
    "id": "...",
    "key": "restrained_tension",
    "version": "1.0.0",
    "profile": {}
  },
  "style_examples": [
    {
      "id": "...",
      "excerpt": "...",
      "teaches": ["..."],
      "scene_tags": ["대치"],
      "fact_eligible": false
    }
  ],
  "policy": {
    "style_examples_are_non_factual": true,
    "reference_names_are_forbidden": true,
    "reference_phrases_must_not_be_copied": true
  }
}
```

`DISCOURSE_REFERENCE` 원문 전체는 이 pack에 넣지 않는다. 승인된 짧은 `VoiceProfileExample.excerpt`만 예시 budget 안에서 포함한다.

### 8.2 우선순위

내용과 표현 우선순위를 분리한다.

내용 권위:

```text
현재 사용자 지시
→ PROJECT_CANON과 잠긴 사실
→ DRAFT_SETTING
→ CANON_EVIDENCE
→ 허용된 추론
→ 모델 창작
```

표현 권위:

```text
현재 원고의 사용자 지시
→ 결과물 종류·시점·시제
→ 선택한 VoiceProfile
→ 승인된 짧은 예시
→ 모델 기본 문체
```

VoiceProfile과 예시는 내용 권위를 가질 수 없다. 프로필 규칙이 시점·시제와 충돌하면 사용자가 글 만들기에서 고른 시점·시제가 우선한다.

### 8.3 토큰 예산

초기 기본값은 구성 가능한 상수로 둔다.

- VoiceProfile: 최대 900 input tokens
- style examples 합계: 기본 1,200, 최대 2,000 input tokens
- 예시 개수: 기본 3개, 최대 5개
- 한 예시가 전체 예산의 50%를 넘지 않음
- 예시가 잘리면 중간 절단하지 않고 해당 예시 전체를 제외

실제 한국어 tokenizer와 Writer context에서 평가한 뒤 설정값을 조정한다. 예시 때문에 locked facts나 현재 본문이 잘리는 구성은 허용하지 않는다.

### 8.4 예시 선택

MVP에서는 다음 결정론적 순서를 사용한다.

1. 사용자가 이번 글에서 직접 고른 예시
2. 현재 결과물·시점·시제와 compatibility가 맞는 예시
3. 현재 전개 계획의 장면 유형과 scene tag가 맞는 예시
4. profile position 순서
5. token budget에 맞는 앞 3~5개

동점은 ID 정렬로 고정해 같은 세션이 재현 가능하게 한다.

## 9. 프롬프트와 모델 호출

### 9.1 Writer 입력 구조

Writer 시스템 프롬프트에 다음 계약을 추가한다.

```xml
<voice_profile>
  승인된 표현 원칙이다. 사실이나 사건을 추가하지 않는다.
</voice_profile>

<style_examples fact_eligible="false">
  표현 방식만 참고한다.
  인물, 지명, 사건, 고유 비유, 긴 어구를 재사용하지 않는다.
</style_examples>

<project_facts>
  현재 원고에서 참으로 사용할 수 있는 사실이다.
</project_facts>
```

예시 안의 명령문, 시스템 프롬프트처럼 보이는 텍스트, XML 태그는 데이터로 escape한다. 참고 글의 지시는 실행하지 않는다.

### 9.2 Planner와 Finalizer

- Planner는 VoiceProfile을 문단 공개 순서를 바꾸는 입력으로 사용하지 않는다.
- Planner는 각 block에 `scene_mode`와 `expression_focus` 추천만 추가할 수 있다.
- Writer는 block의 scene mode에 맞는 예시를 사용한다.
- Finalizer는 최초 VoiceProfile snapshot을 읽기 전용으로 상속한다. 기본 원고 작업 UI는 완성 다듬기에서 다른 프로필이나 모델 기본 문체로 교체하지 않는다.
- Finalizer도 원본 사실 경계와 예시 비사실 정책을 그대로 유지한다.
- 부분 재작성은 현재 문단의 앞뒤 문맥과 원고의 VoiceProfile을 함께 받는다.

### 9.3 Reference Analyzer

Utility는 원문에서 다음 순서로 분석한다.

1. 고유명사·사실·직접 인용 후보 식별
2. 문장 길이·종결·구두점·반복 특성
3. 묘사 대상과 감각 채널
4. 대화와 행동의 관계
5. 문단 전환과 서술 거리
6. 일반화 가능한 표현 원칙
7. 복제 위험과 불확실성

1번 결과는 profile 후보에 넣지 않는다. 분석이 확신하지 못한 항목은 빈 값 또는 uncertainty로 반환하고 그럴듯한 규칙을 창작하지 않는다.

## 10. 필력 점검과 복제 방지

### 10.1 결정론적 검사

LLM 호출 전에 다음을 코드로 검사한다.

- 같은 문장 시작 반복
- 동일·유사 문장 중복
- 문장 길이 분산이 지나치게 낮은 구간
- 같은 종결어미 연속
- 한 문장 문단 과다
- 선택한 avoid pattern의 정확·근사 일치
- 예시문과 긴 공통 문자열
- 예시문과 연속 어절 n-gram 중복
- 참고 원문의 고유명사 유입

초기 복제 경고 기준은 구성 파일로 분리하고 실제 한국어 예시 집합으로 조정한다. 일반 관용구와 프로젝트 정식 명칭은 allowlist로 제외한다. 높은 중복은 원고 저장을 막지 않지만 자동 적용 가능한 제안 상태로 만들지 않고 사용자 확인을 요구한다.

### 10.2 Utility 필력 감사

결정론적 결과와 원고를 Utility에 전달해 다음 JSON Schema로 보완한다.

```json
{
  "issues": [
    {
      "block_id": "...",
      "start_text": "문제 구간 시작 일부",
      "category": "ABSTRACT_EMOTION",
      "reason": "감정을 행동으로 보여 준 뒤 다시 설명한다.",
      "severity": "medium",
      "profile_rule": "description_rules[0]"
    }
  ],
  "strengths": ["..."],
  "uncertainties": ["..."]
}
```

지원 category는 좁게 고정한다.

- `REPETITION`
- `RHYTHM_FLATNESS`
- `ABSTRACT_EMOTION`
- `DIALOGUE_VOICE_COLLISION`
- `EXPOSITION_OVERLOAD`
- `FIGURATIVE_OVERLOAD`
- `CLICHE_OR_SLOP`
- `REFERENCE_OVERLAP`
- `PROFILE_CONFLICT`

Utility의 평가는 문학적 진실이 아니라 검토 후보다. 점수 하나로 합치거나 원고를 자동 수정하지 않는다.

### 10.3 수정 제안

사용자가 issue를 선택해 `AI 수정 제안`을 실행할 때만 Writer를 호출한다.

- 원문 전체와 해당 문단 앞뒤를 읽는다.
- 수정 대상 범위만 반환한다.
- 사실·고유명사·사건 순서를 유지한다.
- 어떤 VoiceProfile 규칙을 개선했는지 표시한다.
- 수정 전/후 비교와 명시적 반영을 거친다.
- 반영 후에도 `초안 전체 저장` 전까지 DB를 바꾸지 않는다.

## 11. 임베딩 도입 조건과 후속 설계

### 11.1 MVP에서 사용하지 않는 이유

- BGE-M3 의미 임베딩은 현재 문장과 주제가 비슷한 예시를 우선할 수 있다.
- 주제 유사성은 참고 작품의 인물·사건·세계 설정 유입 위험을 높인다.
- 임베딩 자체는 Writer에 문체를 주입하지 않으며 결국 검색된 텍스트를 컨텍스트에 넣어야 한다.
- 소수 예시는 사용자 선택과 metadata 정렬이 더 투명하고 재현 가능하다.
- 현재 구현의 병목은 검색이 아니라 VoiceProfile이 API·컴파일러·Writer에 연결되지 않은 것이다.

### 11.2 도입 조건

다음 조건을 모두 충족할 때 후속 단계로 검토한다.

- 한 프로필에 활성 예시가 20개 이상 누적됨
- 고정 예시 3~5개만으로 서로 다른 장면 유형을 커버하지 못한다는 실제 사용자 신호가 있음
- metadata 선택 대비 검색 선택이 A/B에서 사용자 선호를 개선함
- 원문 사실 유입과 표현 복제 gate를 통과함
- 검색 결과와 제외 이유를 UI에서 설명할 수 있음

20개는 제품 운영을 시작하기 위한 임시 기준이며 실제 사용 분포에 따라 조정한다.

### 11.3 후속 검색 구조

```text
현재 plan block
→ 결과물·시점·시제·scene_mode metadata 필터
→ 같은 VoiceProfile의 ACTIVE 예시로 scope 제한
→ lexical + BGE-M3 후보 검색
→ profile compatibility와 generation benefit 재정렬
→ 중복·권한·token budget 제거
→ 상위 2~4개 예시
```

- 전체 소설 원문을 검색 대상으로 두지 않는다.
- `VoiceProfileExample`의 승인 excerpt만 별도 `source_type=voice_example`로 색인한다.
- 기존 factual scope와 다른 source role/type을 사용한다.
- 검색 장애 시 metadata 기본 순서로 축소한다.
- 검색 점수와 무관하게 사용자가 명시 선택한 예시가 우선한다.
- 검색된 예시 ID·점수·embedding version을 GenerationRun에 저장한다.

## 12. 버전·승인·수명주기

### 12.1 상태 전이

```text
참고 분석
CANDIDATE → APPROVED | REJECTED

문체 프로필
DRAFT → APPROVED → DEPRECATED

필력 수정 제안
CANDIDATE → APPLIED | DISMISSED
```

UI에서는 내부 enum 대신 `검토 중`, `사용 가능`, `사용 중지`, `반영됨`, `폐기함`으로 표시한다.

### 12.2 편집과 버전

- 사용 전 DRAFT 프로필은 같은 row를 수정할 수 있다.
- 한 번이라도 PlaybookSession에서 사용한 APPROVED 프로필은 수정 시 새 version row를 만든다.
- 기존 세션과 문서는 사용 당시 version을 유지한다.
- 새 글 만들기는 같은 key의 최신 APPROVED version을 기본 표시한다.
- 이전 version은 상세 이력에서 볼 수 있지만 새 글의 기본 카드에는 노출하지 않는다.
- 프로필 폐기는 기존 문서를 바꾸지 않고 새 선택만 막는다.

### 12.3 공용·프로젝트 범위

- built-in 공용 프로필: `project_id=NULL`, 읽기 전용
- 사용자 공용 프로필: `project_id=NULL`, 로컬 단일 사용자 편집 가능
- 프로젝트 전용 프로필: 현재 project ID
- 프로젝트 전용 참고 원문에서 공용 프로필을 만들 때 원문 연결을 제거하고 승인된 일반화 규칙과 독립 예시만 복사한다.

## 13. 보안·권한·저작물 처리

- 참고 글은 프롬프트 명령이 아니라 데이터로 취급한다.
- 다른 프로젝트 전용 프로필·예시를 조회하거나 연결하지 못한다.
- `ANALYSIS_ONLY` 원문은 Writer·Finalizer·부분 재작성에 전달하지 않는다.
- 직접 생성에 쓰는 예시는 SELF_AUTHORED, LICENSED, PUBLIC_DOMAIN만 허용한다.
- 사용자에게 권한 선택은 법률 판정이 아니라 입력 사용 범위를 통제하기 위한 제품 장치임을 알린다.
- 특정 생존 작가 이름을 기본 프로필이나 추천 카탈로그로 제공하지 않는다.
- 분석 결과는 작가 이름이 아니라 측정 가능한 표현 특성으로 표시한다.
- 원문의 긴 표현과 고유 비유가 후보 JSON에 남지 않도록 Schema·후처리·테스트를 함께 둔다.
- 모든 AI 결과는 사용자 승인 전 CANDIDATE이며 원고나 정식 설정을 자동 변경하지 않는다.

## 14. 마이그레이션 계획

### 14.1 DB 마이그레이션

1. `voice_profiles.project_id` nullable 전환
2. `key`, `version`, `description`, `is_builtin`, `status` 추가
3. 기존 `approved=true`는 `status=APPROVED`, false는 `status=DRAFT`로 backfill
4. 프로젝트 전용·공용 scope에 맞는 partial unique index 두 개 추가
5. `source_analysis_id`를 가능한 경우 ReferenceAnalysis FK로 강화
6. `voice_profile_examples` 테이블과 index 추가
7. `playbook_sessions.voice_selection_mode`, `voice_example_ids` 추가
8. PlaybookSession 프로필 FK의 `SET NULL` 유지
9. API·프론트 전환 뒤 기존 `approved` 컬럼 제거

기존 VoiceProfile backfill:

- `key=reference_{source_analysis_id 앞 8자}` 또는 `voice_{id 앞 8자}`
- `version=1.0.0`
- `description=profile_json.reader_effect` 또는 빈 문자열
- `is_builtin=false`
- `status`는 기존 `approved` 값으로 변환
- scope는 기존 project ID 유지

기존 세션은 `voice_profile_id=NULL`, `voice_selection_mode=model_default`, `voice_example_ids=[]`로 backfill한다. 기존 문서에는 voice 선택이 없었던 것으로 해석하며 과거 생성 결과를 재작성하지 않는다.

### 14.2 API 호환

- 새 voice 필드는 nullable로 추가해 기존 클라이언트 요청을 유지한다.
- 기존 참고 분석 승인 요청 body가 없을 경우 recipe와 voice를 모두 승인하는 동작을 한 번의 호환 기간 동안 유지할 수 있다.
- 프론트 전환 완료 후 명시 선택 body를 필수로 바꾸고 API 문서에 deprecation을 기록한다.

### 14.3 UI 이동 안내

기존 `세계관 자료` 본문의 `이 글의 구성·문체 분석` 버튼은 다음으로 바꾼다.

- 버튼: `문체·전개 분석`
- 승인 결과: `전개 방식에서 보기`, `문체·필력에서 보기` 두 링크
- 기존 분석 결과는 새 `문체·필력` 목록에 자동 표시

중복된 문체 편집 UI를 ConceptPage 상세에 만들지 않는다. 원문에서 분석을 시작할 수는 있지만 프로필 관리는 `문체·필력`에서만 한다.

## 15. 검증 전략

### 15.1 단위 테스트

- VoiceProfile JSON Schema가 허용 필드와 빈 선택 항목을 올바르게 처리한다.
- compatibility는 시점·시제를 덮어쓰지 않는다.
- 사용된 프로필 수정이 새 version을 만든다.
- 사용 중 프로필 삭제가 409를 반환한다.
- ANALYSIS_ONLY 예시는 `use_in_generation=false`를 강제한다.
- 예시 token budget과 최대 개수를 결정론적으로 지킨다.
- 예시 동점 정렬이 같은 결과를 반환한다.
- 예시 n-gram·공통 문자열 검사가 한국어 문장을 처리한다.

### 15.2 API·격리 테스트

- 공용+현재 프로젝트 프로필만 목록에 나타난다.
- 다른 프로젝트 프로필·예시 GET/PATCH/DELETE가 404다.
- 다른 프로젝트 source page를 예시에 연결하지 못한다.
- 승인되지 않은 프로필을 세션에 넣지 못한다.
- 세션 Create/Read/Update가 voice ID를 보존한다.
- 참고 분석에서 voice만 승인하거나 recipe만 승인할 수 있다.
- 삭제·버전 생성에 AuditLog가 남는다.

### 15.3 컨텍스트 컴파일 테스트

- 선택한 프로필 JSON과 version이 pack에 들어간다.
- 선택하지 않으면 숨은 기본 프로필을 삽입하지 않는다.
- `DISCOURSE_REFERENCE` 원문 본문은 pack에 들어가지 않는다.
- 승인 예시는 `fact_eligible=false`다.
- 권한이 없는 예시는 제외되고 warning과 GenerationRun 제외 사유가 남는다.
- locked facts가 예시 token budget보다 항상 우선한다.
- 프로필의 고유명사·원문 긴 표현이 factual pack에 합류하지 않는다.

### 15.4 Writer·감사 테스트

고정된 중립 소재와 seed로 다음을 비교한다.

1. VoiceProfile 없음
2. VoiceProfile만 적용
3. VoiceProfile + 승인 예시 적용

검사 항목:

- 사실 정확도 동일
- 참고 예시 고유명사 0건
- 긴 직접 표현 중복 gate 통과
- 목표 문장 길이 변화·대화 비율·한 문장 문단 비율의 방향성 변화
- 사용자 블라인드 선호
- 프로필 준수 감사와 결정론 지표의 불일치 기록

LLM judge 단독 점수로 PASS를 판정하지 않는다. 결정론 지표와 최소 2인 또는 동일 사용자의 블라인드 쌍대 비교를 함께 사용한다.

### 15.5 Playwright 인수

desktop 1600×900, mobile 390×844/360×844에서 다음을 확인한다.

- 다섯 로컬 탭이 viewport 안에 들어감
- 직접 프로필 생성·수정·복제·안전 삭제
- 예시 분석 모달의 내부 스크롤·고정 footer
- 분석 항목 선택 승인
- 글 만들기 문체 단계의 카드 선택과 모델 기본 문체
- 최종 `표현 설계` 카드의 프로필·예시 수 표시
- 고정 하단 이전/계속 바 유지
- 생성 세션 요청의 voice ID·version 반영
- 원고 작업 필력 점검 → 수정 제안 → 반영/폐기
- pageerror와 가로 overflow 없음

## 16. 관측과 평가 이벤트

로컬 우선 원칙에 따라 외부 전송 없이 애플리케이션 로그 또는 향후 opt-in analytics에서 사용할 이벤트 이름을 고정한다.

| 이벤트 | 필수 속성 |
| --- | --- |
| `voice_profile_created` | scope, source=manual/analysis |
| `voice_profile_approved` | selected_field_count, source_analysis_id 존재 여부 |
| `voice_profile_selected` | profile_id, version, project_id |
| `style_examples_compiled` | selected_count, excluded_count, token_count, selection_mode |
| `prose_audit_completed` | issue_count_by_category, deterministic_count, model_count |
| `prose_revision_applied` | category, profile_version |
| `reference_overlap_warned` | detector, severity, example_id |

원문 excerpt, 전체 원고, 모델 endpoint/key는 이벤트 속성에 기록하지 않는다.

## 17. 구현 작업 패키지

### WP-0. 계약과 fixture

의존성: 없음

- JSON Schema와 enum 확정
- 공용/프로젝트 범위 규칙 확정
- 중립 한국어 문체 fixture 3종과 오염 fixture 작성
- 컨텍스트 pack golden test 작성

완료 조건: 구현 전에 실패하는 계약 테스트가 준비됨.

### WP-1. DB·도메인·API

의존성: WP-0

- Alembic 마이그레이션
- VoiceProfile 모델 확장
- VoiceProfileExample 모델 추가
- Pydantic schema와 CRUD
- PlaybookSession voice 필드 노출
- scope/approval/delete/version AuditLog

완료 조건: API CRUD·격리·마이그레이션 테스트 통과.

### WP-2. 참고 분석과 승인

의존성: WP-1

- REFERENCE_SCHEMA의 voice 후보 구조화
- recipe/voice 선택 승인 요청
- 권한 근거와 ANALYSIS_ONLY 처리
- 분석 결과의 원문 고유명사·긴 문장 후처리

완료 조건: 한 참고 글에서 recipe와 voice를 독립 승인하고 재조회 가능.

### WP-3. 문체·필력 관리 UI

의존성: WP-1, WP-2

- 다섯 번째 로컬 탭
- 카드 목록·범위 표시
- 직접 생성·수정 모달
- 예시 분석·항목 승인
- 예시 CRUD와 권한 표시
- desktop/mobile 접근성

완료 조건: 사용자가 내부 role/JSON을 보지 않고 프로필을 완성할 수 있음.

### WP-4. 글 만들기와 컨텍스트 연결

의존성: WP-1, WP-3

- 글 만들기 선택 단계 추가
- 세션 payload에 voice ID
- 최종 표현 설계 카드
- `compile_context` voice/example pack
- token budget과 제외 warning
- GenerationRun 스냅샷

완료 조건: 선택한 profile/version/examples가 실제 Writer 요청에 기록됨.

### WP-5. Writer·Finalizer·부분 재작성

의존성: WP-4

- writer/finalizer prompt 태그와 권위 계약
- 부분 재작성 voice 문맥
- 완성 다듬기의 최초 voice snapshot 상속
- prompt version 갱신

완료 조건: 초안·완성본·부분 재작성에서 같은 경계 계약을 지킴.

### WP-6. 필력 점검과 수정 제안

의존성: WP-5

- 결정론적 prose audit
- Utility audit Schema
- issue별 Writer 수정 제안
- CANDIDATE 비교·반영·폐기
- source overlap warning

완료 조건: 원고 자동 변경 없이 문제 발견부터 사용자 반영까지 왕복 가능.

### WP-7. 통합 검증·문서·배포

의존성: WP-0~6

- pytest/Ruff/schema/build/Playwright
- 실제 Writer/Utility opt-in A/B
- USER_GUIDE, DATA_MODEL, ARCHITECTURE, LLM_HARNESS 갱신
- ACCEPTANCE_TESTS, IMPLEMENTATION_STATUS, VERIFICATION 동기화
- Compose rebuild와 migration upgrade/downgrade/upgrade

완료 조건: 아래 출시 gate 전부 통과.

### WP-8. 예시 검색 실험

의존성: 출시 후 사용 신호와 도입 조건 충족

- 별도 voice example index scope
- metadata baseline
- lexical+dense 후보와 rerank
- 선택 설명 UI
- metadata 대비 블라인드 A/B

완료 조건: 사용자 선호 개선과 오염 gate를 동시에 통과할 때만 기본 기능으로 승격.

## 18. 출시 Gate

다음 조건을 모두 만족해야 기능을 완료로 표시한다.

1. 사용자가 문체 프로필을 직접 만들고 예시에서 분석할 수 있다.
2. 참고 분석 결과는 사용자 승인 전 생성에 사용되지 않는다.
3. 글 만들기에서 프로필 하나 또는 모델 기본 문체를 명시 선택한다.
4. 선택한 profile ID/version과 실제 예시가 GenerationRun에 기록된다.
5. 다른 프로젝트 프로필·예시는 조회·선택·검색되지 않는다.
6. 참고 원문 전체와 ANALYSIS_ONLY 예시는 Writer에 전달되지 않는다.
7. 예시의 사실·고유명사가 프로젝트 설정 근거로 합류하지 않는다.
8. 초안·완성본·부분 재작성 모두 같은 VoiceProfile 계약을 사용한다.
9. 필력 점검과 수정은 CANDIDATE이며 명시 승인 전 원고를 바꾸지 않는다.
10. 사용 중 프로필의 수정·삭제가 기존 생성 재현성을 깨지 않는다.
11. desktop/mobile에서 로컬 탭·모달·글 만들기 고정 이동 바가 정상 작동한다.
12. 임베딩 장애 또는 미사용 상태에서도 전체 기능이 동작한다.
13. pytest, Ruff, schema validation, Svelte build, 실제 데이터 Playwright가 통과한다.
14. 관련 docs, API schema, migration, tests, 검증 기록이 같은 커밋에 포함된다.

## 19. 위험과 완화

| 위험 | 영향 | 완화 |
| --- | --- | --- |
| 예시 사실 유입 | 세계관 오염 | 별도 테이블·fact_eligible=false·고유명사 검사 |
| 원문 표현 복제 | 저작물·품질 위험 | 짧은 승인 예시·권한 범위·n-gram/LCS 경고 |
| 금지 규칙 과다 | 메마른 산문 | 긍정 규칙 우선·반례 1개 제한·사용자 A/B |
| 프로필과 시점 충돌 | 지시 불안정 | 시점·시제 우선권 고정·compatibility는 추천만 |
| 예시가 사실 budget 잠식 | 설정 누락 | 사실 우선 compiler budget·예시 최대치 |
| 공용 프로필 scope 누출 | 프로젝트 격리 실패 | nullable scope 검증·공용 source 제한 |
| LLM 감사의 자의성 | 잘못된 수정 유도 | 결정론 검사 병행·항목별 제안·자동 적용 금지 |
| 버전 덮어쓰기 | 재현성 상실 | 사용 후 새 version·입력 snapshot |
| 임베딩 주제 편향 | 관련 작품 내용 유입 | MVP 미사용·후속 metadata-first·승인 excerpt만 색인 |
| UI 단계 증가 | 글 만들기 피로 | 선택 사항·모델 기본 문체 카드·한 질문 원칙 유지 |

## 20. 연구 근거와 제품 해석

- [Anthropic의 프롬프트 모범 사례](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#use-examples-effectively)는 출력 형식·톤·구조를 유도할 때 관련성 있고 다양한 구조화 예시 3~5개를 권한다. 제품에서는 이를 긴 원문 한 개가 아닌 짧은 긍정 예시 여러 개로 해석한다.
- [Google Research의 Story Centaur](https://research.google/pubs/story-centaur-large-language-model-few-shot-learning-as-a-creative-writing-tool/)는 창작자가 few-shot 예시를 조합해 고유한 공동 창작 도구를 만드는 접근을 탐구했다.
- [LaMP](https://arxiv.org/abs/2304.11406)와 [Pearl](https://arxiv.org/abs/2311.09180)은 사용자 이력 검색이 개인화 생성에 도움을 줄 수 있지만, 모든 문서가 유익한 것은 아니며 생성 효용에 맞춘 선택이 중요함을 보여 준다. 제품에서는 검색을 초기 필수 기능이 아니라 후속 실험으로 둔다.
- [StyleVector 연구](https://arxiv.org/abs/2503.05213)는 개인 문서 기반 RAG에서 내용 의미와 문체 특성이 얽히는 문제를 지적한다. 제품에서는 원문 전체 검색 대신 일반화 프로필과 승인 excerpt를 분리한다.
- [RisuAI Lorebook](https://github.com/kwaroran/RisuAI/wiki/Lorebook), [NovelAI Lorebook](https://docs.novelai.net/en/text/lorebook/), [SillyTavern Author's Note](https://docs.sillytavern.app/usage/core-concepts/authors-note/)와 [Example Messages](https://docs.sillytavern.app/usage/characters/)는 임베딩 없이 관련 텍스트를 컨텍스트에 직접 삽입해 표현을 유도한다. 제품의 MVP도 명시 선택·구조화 삽입을 우선한다.
- LLM 보조가 개인 산출량이나 세부화를 늘리면서 집단 수준의 표현·아이디어를 동질화할 수 있다는 [연구](https://arxiv.org/abs/2402.01536)와 [후속 분석](https://arxiv.org/abs/2409.11360)이 있다. 제품에서는 이름 기반 작가 모사보다 사용자가 승인한 구체 규칙과 자기 예시를 우선한다.
- 커뮤니티에서는 예시의 상황이 실제 문맥으로 유입될 수 있다는 [경험담](https://www.reddit.com/r/SillyTavernAI/comments/1506swd/)과 과도한 금지 규칙이 산문을 메마르게 할 수 있다는 [논의](https://www.reddit.com/r/SillyTavernAI/comments/1tdp55k/trying_to_ban_slop_makes_the_prose_worse/)가 있다. 이는 실험적 경험담이며 출시 gate의 대체 근거로 사용하지 않는다.

## 21. 최종 권장 순서

실제 개발은 다음 세 덩어리로 나눈다.

1. **운영 가능한 VoiceProfile**: CRUD, 버전, 글 만들기 선택, 컴파일, Writer/Finalizer 연결
2. **안전한 예시 학습**: 참고 분석, 항목 승인, 짧은 예시, 권한·사실 격리, 복제 검사
3. **검토 가능한 품질 개선**: 필력 점검, 부분 수정 제안, A/B와 실제 모델 검증

임베딩 검색은 이 세 덩어리가 실제 사용자 글에서 안정적으로 작동한 뒤 별도 실험으로 진행한다. 이 순서가 현재 미완성 VoiceProfile 기반을 가장 적은 구조 변경으로 살리면서도, 세계관 권위와 사용자 승인 경계를 보존한다.
