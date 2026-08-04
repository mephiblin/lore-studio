# Lore Studio v1.0

Lore Studio는 컨셉 페이지, 방향성 카드, 집필 레시피, 출력 프로필을 분리해 조합하고 로컬 LLM으로 근거가 추적되는 로어 문서를 만드는 단일 사용자용 로컬 작업실입니다. 생성 원고에서 발견한 새 설정은 `CANDIDATE → DRAFT_SETTING → PROJECT_CANON` 승인 단계를 거치며 자동으로 정사가 되지 않습니다.

## 현재 구현

- FastAPI, PostgreSQL 16, `pgvector`, Alembic의 `lore_app`/`lore_vector` 분리 스키마
- Writer/Utility/Vision/Embedding 역할별 OpenAI 호환 로컬 모델 게이트웨이
- BGE-M3 청크 인덱싱, 프로젝트·namespace·source role 격리, FTS/Dense RRF 검색
- 컨셉/관계/방향성/레시피/플레이북 CRUD와 revision·audit log
- Context → editable Plan → LoreBlock Draft → 세 감사 → revision 단계 기록
- 문단 잠금, 부분 재작성 Diff 승인/폐기, 후보 추출/승인, Markdown/HTML/JSON 내보내기
- 이미지 Vision 제안, 참고 글 구조 분석, 내레이션 visual beat/ComfyUI 초안
- 한국어 SvelteKit/Tiptap 데스크톱·모바일 UI와 Playwright 검증

## 빠른 실행

```bash
cd /home/inri/문서/lore-studio
cp .env.example .env
# .env의 모델 alias와 endpoint를 실제 /v1/models 결과에 맞춘다.
docker compose up --build
```

- LAN UI: `http://192.168.200.103:5173` (호스트에서는 `http://localhost:5173`)
- LAN API 문서: `http://192.168.200.103:18000/docs`
- LAN 모델 상태: `http://192.168.200.103:18000/api/v1/models/status`
- PostgreSQL: `127.0.0.1:55432` (Lore Studio 전용 volume)

UI/API는 현재 신뢰하는 LAN 접속을 위해 `0.0.0.0`에 바인딩되며, DB는 로컬호스트에만 유지됩니다. 인증이 없으므로 라우터 포트 포워딩으로 인터넷에 공개하지 마십시오.

현재 DGX 실측 설정은 Gemma 4 26B Writer/Utility/Vision과 BGE-M3 실제 endpoint만 사용합니다. 앱 내 가상 모델 경로는 제거했습니다. Qwen3.5-4B는 namespace 격리 평가 실패로 기본 Utility에서 제외했습니다. 결과는 [`docs/model-evaluations/utility-models.md`](docs/model-evaluations/utility-models.md)에 있습니다.

## 검증

```bash
make test
make lint
make build
make e2e
make test-models
```

기본 테스트는 인터넷과 모델 없이 통과합니다. `make test-models`만 실제 로컬 endpoint가 필요합니다. 운영 명령은 `make migrate`, `make seed`, `make reindex`, `make backup`, 명시적 확인이 필요한 `make restore RESTORE_FILE=... RESTORE_CONFIRM=restore-lore-studio`입니다.

## 문서

- 첫 설치: [`docs/LOCAL_SETUP.md`](docs/LOCAL_SETUP.md)
- 모델: [`docs/LOCAL_MODELS.md`](docs/LOCAL_MODELS.md)
- 사용 순서: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md)
- 운영/백업: [`docs/OPERATIONS.md`](docs/OPERATIONS.md), [`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md)
- 데이터 경계: [`docs/EMBEDDING_ISOLATION.md`](docs/EMBEDDING_ISOLATION.md), [`docs/SECURITY_AND_DATA.md`](docs/SECURITY_AND_DATA.md)
- 개발/상태: [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md), [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md)

모델 파일, `.env`, 사용자 데이터, 백업, 평가 원문과 생성 artifact는 Git에서 제외됩니다.
