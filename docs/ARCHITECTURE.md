# 시스템 아키텍처

## 1. 논리 구조

```text
SvelteKit Web App
├─ Concept Editor
├─ Direction Card Deck
├─ Playbook Composer
└─ Lore Document Editor
        │
        ▼
FastAPI Application
├─ Project / Concept / Card CRUD
├─ Context Compiler
├─ Recipe Engine
├─ Generation Harness
├─ Audit Services
└─ Model Gateway
        │
        ├─ PostgreSQL + pgvector
        ├─ Optional Qdrant / WeKnora
        └─ OpenAI-compatible local LLM server
```

## 2. 권위 저장소

PostgreSQL은 다음의 권위 저장소다.

- 프로젝트
- 컨셉 페이지 메타데이터와 Tiptap JSON
- 페이지 관계
- 방향성 카드
- 집필 레시피 버전
- 플레이북 세션
- 로어 문서와 리비전
- 생성 실행 이력
- 컨셉 승격 후보와 승인 상태

WeKnora나 Qdrant는 원문 파싱·검색·벡터 인덱스를 담당할 수 있지만, 사용자가 승인한 프로젝트 설정의 권위 원본이 되어서는 안 된다.

## 3. DGX Spark 배치

```text
DGX Spark 로컬 NVMe
├─ 실행 중인 LLM 모델
├─ FastAPI / SvelteKit
├─ PostgreSQL
├─ 임베딩·검색 인덱스
└─ 현재 작업 캐시

Synology NAS
├─ 원본 PDF·문서·영상·이미지
├─ 장기 보관 모델
├─ 완성 원고 아카이브
├─ DB 백업
└─ Git 저장소 미러
```

빈번하게 읽는 인덱스와 DB는 DGX 로컬에, 대용량 원본은 NAS에 둔다.

## 4. 모델 게이트웨이

애플리케이션은 특정 런타임을 직접 알지 않는다.

```text
Lore Studio → OpenAI-compatible adapter
                         ├─ llama.cpp
                         ├─ vLLM
                         └─ 기타 호환 서버
```

환경변수로 모델 서버와 이름을 바꾼다. 구조화 출력이 필요한 Planner/Auditor와 장문 Writer가 서로 다른 엔드포인트를 사용하도록 확장할 수 있다.

## 5. 검색 계층의 단계적 확장

### MVP

- PostgreSQL 필터
- 제목·태그·요약 기반 선택
- 사용자가 명시적으로 고른 페이지 중심

### 다음 단계

- PostgreSQL 전문 검색
- BGE-M3 임베딩
- pgvector 또는 Qdrant
- 키워드·Dense 결과 융합
- 다국어 reranker
- 관계·시대 필터

명시적으로 선택한 컨셉 페이지는 검색 점수와 무관하게 컨텍스트의 기준점으로 포함한다.

## 6. 서비스 경계

### Context Compiler

선택된 페이지와 관계 자료를 프롬프트용 증거 팩으로 정리한다. 모델을 호출하지 않는 결정론적 코드가 중심이다.

### Recipe Engine

YAML/JSON으로 버전 관리되는 집필 레시피를 읽고, 이번 소재에 맞는 구성안 요구사항을 만든다.

### Generation Harness

```text
COMPILE_CONTEXT → PLAN → DRAFT → AUDIT → SAVE
```

각 단계의 입력과 출력을 저장한다.

### Auditor

사실 감사와 작문 감사를 분리한다. 감사 결과는 자동 덮어쓰기가 아니라 수정 제안과 Diff로 반환한다.

## 7. 데이터 안전

- LLM 출력은 데이터베이스 명령을 직접 실행하지 않는다.
- 새 설정은 `CANDIDATE`로 저장한다.
- 승인 액션이 `DRAFT_SETTING` 또는 `PROJECT_CANON`으로 승격한다.
- 리비전과 생성 실행을 삭제하지 않고 연결한다.
- 원본 파일 삭제와 인덱스 삭제를 분리한다.
