# 구현 로드맵

마지막 갱신: 2026-08-06
표기: `[x]` 완료, `[~]` 부분 구현, `[ ]` 이후 작업

## v1.0 완료

### 기반

- [x] FastAPI/SvelteKit/PostgreSQL·pgvector/Alembic/Compose
- [x] OpenAI 호환 Writer·Utility·Vision·Embedding 역할 분리
- [x] 프로젝트와 세계관 자료 CRUD, 권위 전이와 리비전

### 매일 쓰는 글 만들기

- [x] 세계관 자료 자유 본문·템플릿·관계·백링크
- [x] 프로젝트 집필 지침과 전개 방식 분리, 공용 기본 방식과 프로젝트별 전개 방식 CRUD·격리
- [x] 주제 → 배경 → 주요 요소 → 갈등 → 집필 지침 → 전개 방식 → 결과물 형태 순서형 선택
- [x] 사용할 설정 확인, 편집 가능한 글의 흐름, 초안 작성
- [x] 제목·상태·전체 문단 원자 저장, 문단 추가·삭제·잠금과 부분 재작성
- [x] 최신 초안 전체를 다시 다듬는 완성 단계와 별도 로어북

### 근거·검색·승인

- [x] FTS와 BGE-M3 Dense RRF 검색
- [x] 프로젝트·namespace·source role·참고 자료 격리
- [x] 문단별 자료명 근거와 Canon/Discourse/Style 감사
- [x] 설정 후보 추출과 사용자 승인 전 자동 정식 설정 편입 금지
- [x] 참고 글 구조 분석과 전개 방식/Voice Profile 후보 승인

### 인터페이스·운영

- [x] 신뢰 LAN 데스크톱·모바일 UI와 360/390px overflow 검사
- [x] Markdown/HTML/JSON 내보내기
- [x] CI, 백업·복구, 모델 평가, offline/실모델 테스트
- [x] 이미지 캡션·태그 제안과 영상 비트/ComfyUI 프롬프트 초안

## v1.0 이후

- [ ] 실제 TTS endpoint adapter와 음성 실측 시간
- [ ] ComfyUI 작업 제출·진행 상태·결과 회수
- [ ] PDF·웹·영상 전사 수집 파이프라인
- [ ] 대형 관계 그래프와 타임라인 전용 화면
- [ ] 반복·유사 전개 감지와 후속 글 추천
- [ ] 다국어 cross-encoder reranker A/B
- [ ] 다중 사용자 인증과 원격 배포 hardening

구조 리팩토링 우선순위와 현재 파일 크기는 루트 [`TASKS.md`](../TASKS.md)를 권위 목록으로 사용합니다.
