# Lore Studio 작업 상태

마지막 갱신: 2026-08-05

## v1.0 완료

- [x] 전용 PostgreSQL/pgvector volume·network·schema와 Alembic up/down/up
- [x] 프로젝트, 카테고리, 컨셉, 관계/백링크, 방향성, 버전 레시피, 플레이북 CRUD
- [x] 권위 상태와 감사 로그, revision, 후보 승인 경계
- [x] Writer/Utility/Vision/Embedding 역할별 실제 모델 routing·health·retry·JSON Schema·streaming
- [x] Utility 모델 합성 평가와 Qwen 탈락/Gemma 제한 fallback 기록
- [x] 프로젝트/namespace/source-role 격리 BGE-M3 청크·재색인·FTS/Dense RRF
- [x] editable plan, 10단계 generation stage, Tiptap LoreBlock와 근거 메타데이터
- [x] 문단 잠금, 실제 부분 재작성 Diff, Canon/Discourse/Style 감사
- [x] 후보 추출과 이번 글만/초안/정사 승인, reference 구조 분석 승인
- [x] 이미지 Vision 제안, video beat/sound cue/ComfyUI 초안, TTS 문자 수 fallback
- [x] Markdown/HTML/JSON 내보내기
- [x] 한국어 반응형 UI, loading/error/empty/progress, Playwright desktop/mobile 검사
- [x] 기본 offline test, 실제 모델 opt-in test, Mock authoring E2E, CI guard
- [x] Makefile, DGX/모델/격리/운영/백업/사용/개발/보안 문서

## v1.0 이후

- [ ] 실제 TTS endpoint adapter와 음성 실측 시간
- [ ] ComfyUI 작업 제출/상태 수집(현재는 안전한 prompt 초안만)
- [ ] 대형 관계 그래프·타임라인 전용 시각화
- [ ] 다중 사용자 인증과 원격 배포 hardening
- [ ] 다국어 cross-encoder reranker A/B(현재는 lexical + BGE-M3 RRF)

이 항목들은 현재 단일 사용자 로컬 문서 중심 v1.0의 완료 조건을 막지 않습니다.
