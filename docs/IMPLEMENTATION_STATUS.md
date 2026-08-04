# Lore Studio v1.0 구현 상태

마지막 갱신: 2026-08-05 (Asia/Seoul)  
기준 리비전: `facfc4f Add Lore Studio starter project`  
상태: **구현 진행 중 — starter 골격에서 실제 로컬 모델 기반 v1.0으로 전환**

## 완료 계약

주 사용자는 DGX Spark에서 자신의 세계관 자료를 축적하고 실제 로컬 LLM으로 장문 로어를 매일 집필하는 단일 사용자다. 핵심 작업은 컨셉 페이지, 방향성 카드, 집필 레시피, 출력 프로필을 분리해 플레이북으로 조합하고, 근거가 추적되는 편집 가능한 문서를 만든 뒤 새 설정을 사용자 승인으로만 승격하는 것이다.

현재 작업 범위는 PostgreSQL/pgvector와 Alembic, 역할별 로컬 모델 게이트웨이, 하이브리드 검색, 생성 단계 기록, 권위 승격 경계, LoreBlock 편집/부분 재작성/감사/후보/내보내기 API와 실제 한국어 UI, 운영·백업·모델 평가·CI 문서 및 테스트다. 외부 클라우드 LLM, 다중 사용자 인증, 모델 파일 자체의 배포는 v1.0 비목표다.

완료 판정은 첨부 요구사항의 25개 완료 조건, `docs/ACCEPTANCE_TESTS.md`, 실제 Writer/Utility/Embedding 통합 실행, Mock 없이 수행한 대표 생성, 외부 모델 없이도 통과하는 기본 CI를 모두 증거로 남겼을 때만 한다.

## 2026-08-05 최초 조사 결과

| ID | 심각도 | 관찰된 문제 | 직접 증거 | 구현 순서 |
|---|---|---|---|---|
| LS-001 | P1 | 운영 DB가 마이그레이션 없이 런타임 `create_all`에 의존하고 pgvector/스키마 분리가 없다. | `backend/app/main.py`, `backend/app/db.py`, Alembic 디렉터리 없음 | 1 |
| LS-002 | P1 | 모델 게이트웨이가 단일 `MODEL_*` 프로필만 지원하고 endpoint/model/sampling/capability 기록과 fallback·streaming이 없다. | `backend/app/services/model_gateway.py` | 2 |
| LS-003 | P1 | 권위 승격 API, 감사 로그, revision 연결, 후보 승인 경계가 API에서 강제되지 않는다. | `backend/app/models.py`, `backend/app/api/router.py` | 3 |
| LS-004 | P1 | 검색·전문 검색·임베딩·재색인 상태와 프로젝트/네임스페이스 격리가 구현되지 않았다. | 검색 서비스와 embedding 테이블 없음 | 4 |
| LS-005 | P1 | 프론트 production build가 실패한다. | `npm run build`: `$env/static/public`에 `PUBLIC_API_BASE_URL` 미정의 | 5 |
| LS-006 | P1 | UI는 생성 골격뿐이며 구성안 편집, LoreBlock, 부분 재작성 Diff, 감사, 후보 승격, 내보내기가 없다. | `frontend/src/routes/*` 직접 점검 | 6 |
| LS-007 | P2 | Compose가 `.env` 없이는 config 검증도 실패하고 요구된 전용 volume/network/host port가 없다. | `docker compose config --quiet` 실패 및 `docker-compose.yml` | 1 |
| LS-008 | P2 | 테스트가 3개뿐이고 API/마이그레이션/권위/검색/실제 모델/E2E 검증이 없다. | `backend/tests` | 전 단계 병행 |
| LS-009 | P2 | v1.0 운영·로컬 모델·임베딩 격리·보안·사용자 문서가 없다. | `docs/` 파일 목록 | 전 단계 병행 |

## 베이스라인 실행 기록

- Python 3.12.3, Node 22.23.1, Docker 29.2.1, Compose 5.0.2 확인.
- 격리 환경 `.venv`에 backend dev 의존성 설치 후 기존 테스트: `3 passed`.
- `npm install`: 성공, 123 packages. `npm run build`: 실패(LS-005).
- 최초 Compose config: `.env` 부재로 실패. `make bootstrap` 후 config 파싱 성공.
- 실제 로컬 Writer: `http://127.0.0.1:8080/v1`, `Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP-Q4_K_M`; 짧은 한국어 completion 성공.
- 실제 Utility: `Qwen3.5-4B-Q4_K_M`; 직접 endpoint와 새 역할별 게이트웨이에서 JSON object 응답을 파싱해 통과.
- 실제 Embedding: `http://127.0.0.1:8081/v1`, BGE-M3; 한국어 embedding 응답 성공(반환 차원은 구현된 평가에서 자동 판정 예정).
- 로컬에 Gemma 4 26B/31B, Qwen3.5 4B, Qwen3.6 35B-A3B, BGE-M3 GGUF와 호환 mmproj가 이미 있어 임의 다운로드는 하지 않는다.

## 구현 순서와 재개 지점

1. 역할별 모델 프로필과 실제 health/capability/구조화 출력/streaming 클라이언트 구현 및 실제 모델 평가.
2. PostgreSQL 전용 Compose 격리, Alembic 초기 마이그레이션, v1 도메인 테이블과 권위 상태 서비스.
3. CRUD/관계/검색/재색인/플레이북/단계형 생성/감사/후보/내보내기 API와 테스트.
4. production build 가능한 SvelteKit 작업공간 UI, LoreBlock 문서 편집과 핵심 E2E.
5. 운영 스크립트·CI·문서·백업/복구, Compose 실제 기동과 전체 재감사.

다음 정확한 명령:

```bash
cd /home/inri/문서/lore-studio
.venv/bin/pytest -q backend/tests
cd frontend && npm run build
```

## 현재 외부 검증 경계

모델 파일과 실제 엔드포인트는 발견되어 새 애플리케이션 게이트웨이를 통한 Writer, Utility JSON object, BGE-M3 1024차원 실호출을 검증했다. Utility 전체 평가셋, JSON Schema 모드, 장문 Writer 생성 품질, Vision 입력, PostgreSQL/pgvector 통합과 브라우저 E2E는 아직 검증 전이며 완료로 표시하지 않는다.
