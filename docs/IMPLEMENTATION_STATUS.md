# Lore Studio v1.0 구현 상태

마지막 갱신: 2026-08-07
기준: `65c44fb` (`main`)까지의 실제 local-first v1.0 구현
상태: **완료 — 실제 모델 모드로 실행 중**

## 완료 기능

- 전용 PostgreSQL/pgvector/Alembic, 22개 도메인·검색 테이블과 revision/audit
- 역할별 Writer/Utility/Vision/Embedding gateway와 공개-safe health, retry, structured output, SSE
- 프로젝트/namespace/source role 격리 하이브리드 검색과 명시적 index job
- 권위 전이, 프로젝트별 자료 종류/세계관 자료/관계/집필 지침/전개 방식/글 만들기 기록 API
- editable Plan, 10 generation stages, LoreBlock, 세 감사, 잠금/부분 Diff
- 후보 추출/명시 승인, 참고 구조 분석/승인, 이미지 Vision, export/video fallback
- 프로젝트 중심 전역 메뉴와 모든 주요 화면의 프로젝트 선택·추가
- 작업 흐름·모델 상태 중복을 제거한 콤팩트 프로젝트 허브, 300px 노션형 커버 카드, 커버 이미지 축소·교체·제거
- 글 만들기 추천/전체 바 제거, 자료 선택 카드를 프로젝트 카드와 같은 16:9 이미지·본문·하단 메타 구조로 통일, 주요 메뉴 색상의 선택 상태 적용
- 세계관 자료/프로젝트 자료 종류/프로젝트 집필 지침 분리, 이름 기반 관계 생성·삭제와 자연어 관계 표시
- 주제·배경·주요 요소·갈등·집필 지침·공유 전개 방식·결과물 형태를 한 질문씩 진행하는 설문형 글 만들기, 시점·시제 생성 기록 저장
- 프로젝트별 집필 지침(DirectionCard)과 프로젝트 독립 전개 방식(WritingRecipe)을 별도 단계와 API 범위로 격리
- UI 핵심 용어를 `세계관 자료 / 집필 지침 / 전개 방식 / 결과물 형태 / 초안 / 완성본 / 로어북`으로 통일하고 정보 구조 문서에 사용 규칙 고정
- `사용할 설정 확인 → 글의 흐름 만들기 → 초안 작성`의 쉬운 생성 동선, 문단 방식 툴팁, 압축형 흐름 편집, 생성 초안 자동 열기
- `초안 편집 → 완성 설정 → 완성본 만들기`의 단계형 원고 작업, 제목·상태·문단 추가/수정/삭제 원자 저장, 미저장 표시, 단계·프로젝트·초안 전환 전 자동 저장, 수정 가능한 완성 설정, 별도 로어북 저장, 초안 변경 감지와 로어북 export
- 프로젝트 전환 API 응답 경합 방지와 최신 선택 프로젝트만 반영하는 화면 상태 보호
- 반응형 한국어 UI, 가로 잘림 없는 모바일 하단 메뉴·단계 그리드, 자료 선택 후 본문 이동, 모바일 원고 선택·문단 편집, 자료 종류 설정 목록·접이식 생성 폼·단계별 호버/클릭 설명, desktop/mobile Playwright, 정보 구조 문서, Makefile/CI/운영 문서
- 73개 이상 자료에서도 프로젝트 자료 종류별 단계 추천 18개·전체 전환·점진 더 보기로 유지되는 글 만들기와 높이가 제한된 자료 보관함
- 모바일 전체 화면 프로젝트 생성 창, 첫 화면 프로젝트 우선 배치, 원고 도구 바로 가기, 로어북 읽기/편집 모드 분리와 줄바꿈 제목

## 실제 환경 증거

2026-08-06 현재 Compose는 가상 모델 경로 없이 `/models/status`에서 Gemma Writer/Utility/Vision과 BGE-M3 실제 endpoint가 모두 `available=true`임을 확인합니다. 2026-08-05 대표 인수 실행은 5-block 계획, 1,039자/5 LoreBlock 원고, 실제 Diff, 2 후보, 세 export, Vision caption, Dense 검색을 완료했습니다. SSE progress/complete도 실제 Writer로 통과했습니다. 공유 `원인에서 파급으로` 프리셋의 실제 Utility 재검증은 `ORIENT → ANCHOR → EXEMPLIFY → ESCALATE → INTERPRET` 순서의 5-block 계획을 반환했습니다.

Utility 9-case 결과는 Qwen3.5-4B가 namespace 누출로 탈락했고 Gemma4-26B가 88.9%와 격리 gate 통과로 선택됐습니다. source-role 모델 판단은 완전하지 않으므로 애플리케이션의 결정론적 권위 코드가 항상 최종 판정을 합니다.

## 최종 검증

- Ruff PASS
- pytest `13 passed, 3 skipped` (실제 endpoint opt-in tests는 기본 run에서 skip)
- 실제 모델 opt-in `3 passed` (Writer/Utility, Embedding, Vision)
- bundle/schema/YAML PASS
- Svelte production build PASS
- 실제 데이터 Playwright `26 passed, 6 skipped` (1600×900/390×844·360×844, 73개 자료 목록 높이, 단계 이동·설명 툴팁, 프로젝트별 자료 종류 편집, 모바일 프로젝트 생성 창, 읽기/편집 모드, 기존 생성 gate·원고 저장·완성 설정·로어북 분리 포함)
- 모델 서비스 미연결 UI E2E `10 passed`
- Compose build/up 및 DB health PASS
- PostgreSQL Alembic upgrade/downgrade/upgrade PASS

## 남은 제한

실제 TTS와 ComfyUI job 제출 endpoint는 설정되지 않아 TTS 글자 수 추정과 ComfyUI prompt 초안 fallback만 검증했습니다. 이는 v1.0의 외부 서비스 선택 기능이며 앱 실패 원인이 되지 않습니다. 신뢰 LAN 접속은 허용했지만 다중 사용자 인증/인터넷 노출, 관계 그래프, cross-encoder reranker는 v1.0 이후 항목입니다.

## 현재 실행과 다음 확인

```bash
cd /home/inri/문서/lore-studio
docker compose ps
curl http://127.0.0.1:18000/api/v1/models/status
make test && make lint && make e2e
```

LAN UI는 `http://192.168.200.103:5173`, API 문서는 `http://192.168.200.103:18000/docs`입니다. PostgreSQL은 계속 `127.0.0.1:55432`에만 바인딩됩니다. BGE 검증용 호스트 서버는 8010 포트에서 실행 중이며 운영 재부팅 후 `docs/LOCAL_MODELS.md` 명령으로 다시 시작해야 합니다.
