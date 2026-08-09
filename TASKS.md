# Lore Studio 작업 상태

마지막 갱신: 2026-08-06
현재 기준: `65c44fb` (`main`)

## v1.0 완료

- [x] 전용 PostgreSQL/pgvector volume·network·schema와 Alembic up/down/up
- [x] 프로젝트별 자료 종류 생성·수정·안전 삭제, 세계관 자료, 관계/백링크, 프로젝트 집필 지침, 공용·프로젝트 전개 방식, 글 만들기 기록 CRUD
- [x] 권위 상태와 감사 로그, revision, 후보 승인 경계
- [x] Writer/Utility/Vision/Embedding 역할별 실제 모델 routing·health·retry·JSON Schema·streaming
- [x] Utility 모델 합성 평가와 Qwen 탈락/Gemma 제한 fallback 기록
- [x] 프로젝트/namespace/source-role 격리 BGE-M3 청크·재색인·FTS/Dense RRF
- [x] editable plan, 10단계 generation stage, Tiptap LoreBlock와 근거 메타데이터
- [x] 문단 잠금, 실제 부분 재작성 Diff, Canon/Discourse/Style 감사
- [x] 설정 후보 추출과 이번 글만/설정 초안/정식 설정 승인, 참고 글 구조 분석 승인
- [x] 이미지 Vision 제안, video beat/sound cue/ComfyUI 초안, TTS 문자 수 fallback
- [x] Markdown/HTML/JSON 내보내기
- [x] 초안 제목·상태·전체 문단 원자 저장, 문단 추가/삭제, 단계·프로젝트·초안 전환 전 자동 저장
- [x] 최신 초안과 수정 가능한 완성 설정을 다시 Writer에 전달하고 별도 로어북 완성본으로 저장
- [x] 프로젝트 응답 경합 방지와 UI 핵심 용어 통일
- [x] 한국어 반응형 UI, loading/error/empty/progress, Playwright desktop/mobile 검사
- [x] 기본 offline test, 실제 모델 opt-in test, 모델 미연결 UI E2E, CI guard
- [x] Makefile, DGX/모델/격리/운영/백업/사용/개발/보안 문서

## v1.0 이후

- [ ] 실제 TTS endpoint adapter와 음성 실측 시간
- [ ] ComfyUI 작업 제출/상태 수집(현재는 안전한 prompt 초안만)
- [ ] 대형 관계 그래프·타임라인 전용 시각화
- [ ] 다중 사용자 인증과 원격 배포 hardening
- [ ] 다국어 cross-encoder reranker A/B(현재는 lexical + BGE-M3 RRF)

## 구조 정리 후보

2026-08-06 책임 수와 변경 충돌 가능성을 기준으로 점검했습니다. 동작 변경과 한꺼번에 섞지 않고 아래 순서로 별도 진행합니다.

- [ ] P1 `backend/app/api/router.py`(1,440줄, 함수 77개): 프로젝트·자료·집필 지침·글 만들기·원고·로어북·분석 라우터로 분리
- [ ] P1 `frontend/src/routes/editor/+page.svelte`(460줄, 함수 22개): 세계관 자료 작업공간과 집필 지침 작업공간을 컴포넌트·상태 모듈로 분리
- [ ] P2 `backend/app/services/harness.py`(694줄): 계획, 초안 생성, 완성본 생성, 실행 기록 책임을 서비스로 분리
- [ ] P2 `frontend/src/routes/playbook/+page.svelte`(353줄, 함수 23개): 자료 선택 단계, 집필 지침, 전개 방식, 결과물 형태, 검토 단계를 컴포넌트로 분리
- [ ] P2 `frontend/src/routes/documents/+page.svelte`(321줄, 함수 19개): 초안 저장 상태·문단 편집기와 완성 설정 패널을 컴포넌트로 분리하되 3단계 흐름은 route가 소유
- [ ] P3 `frontend/src/styles.css`(575줄): 공통 토큰·앱 셸과 화면별 스타일시트로 분리하되 위 컴포넌트 분리 뒤 진행

리팩토링은 동작 변경과 분리해 진행합니다. 특히 원고 저장의 원자성, 잠금 문단 보호, 단계 이동 자동 저장을 먼저 회귀 테스트로 고정한 뒤 컴포넌트를 추출합니다.

이 항목들은 현재 단일 사용자 로컬 문서 중심 v1.0의 완료 조건을 막지 않습니다.
