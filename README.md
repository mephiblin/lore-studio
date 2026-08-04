# Lore Studio Starter

로컬 LLM과 사용자가 함께 세계관을 축적하고, 그 재료를 조합해 지속적으로 로어 글을 만드는 **로컬 우선 창작 작업실**의 실행 가능한 MVP 골격입니다.

이 저장소는 다음 네 요소를 분리해 다룹니다.

1. **컨셉 페이지** — 인물, 장소, 사건, 규칙, 다른 IP 참고자료 등 “무엇을 알고 있는가”
2. **방향성 카드** — 이번 글에서 “무엇이 일어나거나 어떤 의미를 향해야 하는가”
3. **집필 레시피** — 정보를 “어떤 순서와 작문 방식으로 독자에게 풀어낼 것인가”
4. **플레이북** — 위 요소들을 선택·무작위 조합하고 분량·상세도·창작 자유도를 설정해 실제 생성을 실행하는 화면

생성된 글에서 새 설정을 추출할 수 있지만, **사용자가 승인하기 전에는 프로젝트 정사로 자동 편입되지 않습니다.**

## 포함된 것

- 한국어 제품·설계·철학 문서
- FastAPI + PostgreSQL 기반 백엔드 골격
- SvelteKit + Tiptap 기반 프론트엔드 골격
- OpenAI 호환 로컬 모델 게이트웨이
- 컨텍스트 컴파일러 및 계획→집필 하네스
- 컨셉 페이지·방향성 카드·집필 레시피·플레이북·로어 문서 데이터 모델
- 기본 페이지 템플릿과 네 가지 집필 레시피
- Docker Compose 및 데모 시드 스크립트
- 코딩 에이전트용 `AGENTS.md`와 우선순위 백로그

## 빠른 실행

```bash
cp .env.example .env
# 모델 없이 UI/흐름부터 볼 때는 MOCK_MODEL=true 유지
# 실제 로컬 모델을 쓸 때는 MODEL_BASE_URL, MODEL_NAME을 수정하고 MOCK_MODEL=false

docker compose up --build
```

- 웹 UI: `http://localhost:5173`
- FastAPI 문서: `http://localhost:8000/docs`
- 상태 확인: `http://localhost:8000/api/v1/health`

데모 데이터를 넣으려면 다음을 실행합니다.

```bash
python scripts/seed_demo.py
```

## DGX Spark 로컬 모델 연결 예시

vLLM 또는 llama.cpp가 호스트의 8001 포트에서 OpenAI 호환 API를 제공한다고 가정합니다.

```env
MOCK_MODEL=false
MODEL_BASE_URL=http://host.docker.internal:8001/v1
MODEL_API_KEY=local
MODEL_NAME=your-local-model-name
```

Linux Docker에서 `host.docker.internal`을 사용할 수 있도록 Compose에 `host-gateway`가 포함되어 있습니다.

## 현재 MVP 범위

현재 골격은 다음 흐름을 구현합니다.

```text
프로젝트 생성
→ 컨셉 페이지 작성
→ 방향성 카드 작성
→ 플레이북에서 소재·방향·집필 레시피 선택
→ 컨텍스트 미리보기
→ 구성안 생성
→ 로어 원고 생성
→ 로어 문서 저장
```

다음 기능은 설계와 확장 지점은 포함하지만 완성 구현은 아닙니다.

- 문단별 근거 칩과 세밀한 Canon 감사
- 하이브리드 검색·임베딩·리랭커
- 문단 잠금 및 부분 재작성 Diff UI
- 참조 글에서 작문 플레이북 자동 추출
- 생성 원고에서 컨셉 후보 추출·승인 UI
- 타임라인·관계 그래프
- TTS 길이와 영상 비트 연동

## 문서 읽는 순서

1. [`docs/PROJECT_SPECIFICATION.md`](docs/PROJECT_SPECIFICATION.md)
2. [`docs/WRITING_SYSTEM.md`](docs/WRITING_SYSTEM.md)
3. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
4. [`docs/LLM_HARNESS.md`](docs/LLM_HARNESS.md)
5. [`TASKS.md`](TASKS.md)

## 저장소 구조

```text
lore-studio-starter/
├─ docs/                 제품·작문·아키텍처 명세
├─ config/               페이지 템플릿·레시피·출력 프로필·프롬프트
├─ schema/               JSON Schema
├─ backend/              FastAPI 애플리케이션
├─ frontend/             SvelteKit 애플리케이션
├─ scripts/              데모·검증 스크립트
└─ sample/               원본 IP와 무관한 예시 데이터
```

## 설계의 핵심 문장

> 에디터는 세계관의 재료와 가능성을 축적하고, 방향성 카드는 이번 창작의 의도를 제공하며, 집필 레시피는 정보를 이야기로 풀어내는 방법을 정하고, 플레이북은 이들을 매번 새롭게 조합해 다음 로어를 생산한다.
