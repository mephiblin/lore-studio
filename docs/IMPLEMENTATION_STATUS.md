# Lore Studio v1.0 구현 상태

마지막 갱신: 2026-08-12
기준: `agent/project-taxonomy-and-ui-polish` 브랜치의 실제 local-first 구현
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
- 자료 종류·집필 지침·전개 방식의 생성·수정을 AI 작성과 같은 내부 스크롤·고정 저장 모달로 통일, 집필 지침 세부 규칙 상시 노출, 패널 경계를 벗어나도 잘리지 않는 viewport 고정형 도움말 오버레이
- 글 만들기 본문 스크롤과 분리되어 `확인·작성`까지 유지되는 하단 `이전 / 계속` 이동 바(데스크톱 작업면 하단·모바일 전역 메뉴 위 고정)
- 새 세계관 자료 생성은 이름·자료 종류만 입력받고 일반 설정 역할(`DRAFT_SETTING`)을 자동 적용해 내부 권위 선택을 기본 흐름에서 숨김
- 세계관 자료 양산은 기본 `Qwen 기획 → Gemma 집필 → 동시 작업 4개`를 자동 적용하고 참고 자료·자료 종류·씨앗 수·길이만 먼저 고르게 함. 단일 기획 에이전트가 차별점·근거가 붙은 6–30개 씨앗을 제안하고, 사용자가 수정·선택한 1–10개만 별도 동시성 한도에서 본문으로 생성함. 결과에는 자료 종류별 핵심 항목·계승 사실·새 설정 후보·글자 수가 포함되며, 명시 선택 전 저장되지 않고 저장 후에도 `CANDIDATE` 유지. planner/worker별 모델·길이·동시성 GenerationRun과 부분 실패 기록
- 세계관 자료 Tiptap 툴바의 선택 영역 `AI 수정`과 전체·현재 위치·이어쓰기 `AI 작성`, 두 panel/modal의 요청별 Gemma/Qwen 선택과 실제 모델 표시·무 fallback 고정 호출, 전체 본문·선택부 앞뒤를 먼저 분석하는 문맥 기반 수정, 최소·목표 길이와 확대된 출력 예산을 적용하는 `더 자세히 (약 2배)`, 실행별 임시 참고 자료 선택, 본문 변경 감지, 진녹색·금색 고대비 `CANDIDATE` 비교·명시 반영, 저장 전 상태 보존
- 주제·배경·주요 요소·갈등·집필 지침·공용/프로젝트 전개 방식을 한 질문씩 진행하고 결과물 종류·시점·시제·분량을 원고 견본과 의미 카드로 고르는 글 만들기, 시점·시제 생성 기록 저장
- 프로젝트별 집필 지침(DirectionCard)과 전개 방식(WritingRecipe)을 별도 단계로 유지하고, 공용 기본 방식과 현재 프로젝트 소유 방식만 선택하도록 API 범위 격리
- 문체·필력(VoiceProfile) 검토본·승인·중지·사용 후 새 버전, 공용/프로젝트 범위, 권리 근거가 있는 짧은 예시 관리와 분석 전용 예시의 Writer 격리
- 글 만들기의 명시적인 `문체·필력` 단계, Context compiler의 비사실 표현 pack, Writer·Finalizer·부분 재작성의 동일 snapshot, 원고 해시 기반 필력 점검과 항목별 승인형 수정 제안
- 자료 종류와 전개 방식을 프로젝트·글 만들기와 같은 260–300px 카드 갤러리로 통일, 자료 종류의 중복 분류 기준 제거, `required_moves` 실제 순서만 카드·계획·감사에 사용하고 단계 목적은 고정 Move 사전에서 자동 파생
- UI 핵심 용어를 `세계관 자료 / 집필 지침 / 전개 방식 / 결과물 형태 / 초안 / 완성본 / 로어북`으로 통일하고 정보 구조 문서에 사용 규칙 고정
- 주제·소재·집필 원칙·표현 설계 카드와 `글의 흐름 설계 → 초안 작성`을 합친 최종 원고 설계 화면, 작성 경계 자동 컴파일, 인라인 흐름 편집, 문단 방식 툴팁, 생성 초안 자동 열기
- 소설·수필·분석 보고서용 공용 집필 지침 프리셋, 전개 방식, 결과물 형태, 예시 원문 없는 읽기 전용 문체·필력 프로필과 선택 분량에 맞춘 문단 예산 합계 정규화
- `세계 내부 구술` 결과물, `현장 징후에서 경고로` 전개 방식, `현장 증언 문체` 공용 프로필. 화자의 목격·전언·추측과 지식 범위, 완성 원고 출력, 경고·거래·행동 결말을 분리된 자산으로 제공하고 전용 `max_tokens`나 고정 글자 수는 추가하지 않음
- OpenWebUI의 상세 작가 프롬프트를 Gemma4 26B로 실검한 뒤 분해한 결과물 9종·전개 방식 11종·문체 9종. 새 `상징적 우화 단편 / 공간 순례에서 귀결로 / 의례적 고딕 이야기꾼`의 고정 반복 신호·정사 경계·상징 해설 금지 계약 포함
- `정밀 / 균형 / 표현 풍부` 생성 성향과 온도·Top P·Top K·반복 억제·새 화제 허용의 고급 override. Writer 적용, 보수적 Finalizer 파생, GenerationRun 실제 파라미터 snapshot, 기존 글자 수 분량 계약과 분리
- `초안 편집 → 완성 다듬기 → 완성본 만들기`의 단계형 원고 작업: 콤팩트 제목 toolbar와 8px 문단 리듬, 재작성·문장 점검·설정 후보 중 하나만 여는 원고 도구, 원본 설계 읽기 전용 기준표와 보강 목표·강도·분량 방향 카드, 반복 수정 버튼 없는 최종 요약, 최신 편집 초안 전체를 입력으로 쓰는 Finalizer, 모바일 단계 상단 복귀, 제목·상태·문단 원자 저장, 별도 로어북 저장과 초안 변경 감지
- 프로젝트 전환 API 응답 경합 방지와 최신 선택 프로젝트만 반영하는 화면 상태 보호
- 반응형 한국어 UI, 가로 잘림 없는 모바일 하단 메뉴·단계 그리드, 자료 선택 후 본문 이동, 모바일 원고 선택·문단 편집, 자료 종류·집필 지침·전개 방식 카드 갤러리와 생성·수정 모달, 단계별 호버/클릭 설명, desktop/mobile Playwright, 정보 구조 문서, Makefile/CI/운영 문서
- 73개 이상 자료에서도 전체 미배정 자료를 18개씩 점진적으로 여는 글 만들기와 높이가 제한된 자료 보관함
- 모바일 전체 화면 프로젝트 생성 창, 첫 화면 프로젝트 우선 배치, 원고 도구 바로 가기, 로어북 읽기/편집 모드 분리와 줄바꿈 제목
- 모바일 390×844·360×844 전용 감사 계약, 세계관 본문의 문서 scroll 소유권·긴 AI 선택 폭 제약·viewport sticky 검토 패널, 360px 프로젝트 도구 한 행·글 만들기 5+4 단계·원고 3단계 압축
- 모바일 로어북의 `/lorebook` 목차 → `?entry=<id>` 독립 읽기 → `목차로` 복귀, 제목·분량·날짜 목록, 읽기 전용 상단 복귀 bar, 네 테마 계승
- 결과물 견본의 주제·배경·주요 요소·갈등·변수·집필 지침·전개 방식·문체·필력과 형식·시점·시제·분량을 분리 장부로 실시간 요약, 확인 항목의 수정 후 즉시 복귀, 실제 작성 진행에 따른 2단계 완료 색상
- 세계관 자료의 저장 후 읽기 모드·명시적 글 편집, 프로젝트·세계관 자료·로어북 삭제, 출처 초안을 보존하는 로어북 삭제 API·감사 기록
- 글 만들기 대규모 자료 카드의 비겹침 방지·독립 스크롤·전역 하단 바와 겹치지 않는 고정 `자료 더 보기`
- 로어북 `.page-tools` 왼쪽의 브라우저 로컬 열람 테마 4종: 기존 노말, 밝은 양피지·굵은 적갈색 판타지아, 단순 선형 암부·형광 녹색·배경 글리치 메카니컬, 공포 질감 없는 남색 도시 네온 어반 판타지, 이미지보다 어두운 작업면 여백과 공통 진녹색·금색 `글 편집`, 읽기/편집 고대비·번호·금색 ring·ARIA 선택 표현
- 6,000자 미만의 목표 글자 수 기반 `max_tokens` 안전 상한·95% 미달 시 마지막 문단 직전의 새 설정 없는 최대 3회 보강·미달 저장 차단, 6,000자 이상 초안·완성 보강의 전개 블록별 이어쓰기와 실제 글자 수 95% 저장 gate, 호출·목표·실제 분량 감사 기록
- 긴 로어북 본문의 reader 내부 스크롤과 출처 초안·접힌 생성 설정을 합친 단일 출처 카드
- `$lore-studio-ui-safety` 프로젝트 로컬 skill과 읽기 전용 정적 preflight: UI 계약·변경 체크리스트 기반 반복 점검, 5개 생명주기 route와 `/settings` 유틸리티·migration head·manifest·API 경유 규칙 확인, 기능 계약과 점검 절차의 변경 범위에 따른 문서·테스트·skill 동기화
- Writer·Utility·Vision·Embedding 역할별 OpenAI 호환 모델 연결 시험·저장·`.env` 복귀 화면. Writer·Utility·Vision은 Qwen·Gemma를 독립 선택하고 권장 분담(Writer=Gemma, Utility/Vision=Qwen)을 적용할 수 있으며 API key 원문은 브라우저·감사 로그에 반환하지 않고 Embedding을 보존
- Qwen·Gemma vLLM의 서버 기본 Thinking OFF와 앱 profile OFF를 일치시키되 native MTP는 유지. 생성 호출은 대화 history 없는 새 요청을 기본으로 하고, AI 본문 작성은 현재 본문·작성 경계·명시 선택 참고만 전달하며 실패한 형식 응답을 다음 시도에 재사용하지 않음

## 실제 환경 증거

2026-08-11 현재 Compose는 `/models/status`에서 Gemma Writer, Qwen Utility/Vision, BGE-M3 Embedding이 모두 `available=true`입니다. 두 vLLM은 loopback에 유지하고 Docker backend는 bridge 전용 socket proxy로 접근합니다. 실제 ModelGateway에서 Gemma `LORE_OK`, Qwen `{"status":"ok"}`와 opt-in Writer/Utility·Vision·Embedding 3건을 통과했습니다. 세계관 본문 AI의 명시 선택 실검증도 Qwen 수정=`qwen36-heretic-mtp@18091`, Gemma 초안=`gemma4-26b-heretic-mtp@18093`로 각각 기록됐고, 저장 전 제안과 원문 불변 계약을 지켰습니다. 실제 현장 구술 검증은 임시 프로젝트에서 `ORIENT → ANCHOR → EXEMPLIFY → WITHHOLD → ESCALATE → STING`의 계획과 Gemma 원고를 생성했고, 은종의 주인을 확정하거나 내부 소제목을 노출하지 않았으며 검증 자료는 삭제했습니다. 2026-08-05 대표 인수 실행은 5-block 계획, 1,039자/5 LoreBlock 원고, 실제 Diff, 2 후보, 세 export, Vision caption, Dense 검색을 완료했습니다. SSE progress/complete도 실제 Writer로 통과했습니다. 공유 `원인에서 파급으로` 프리셋의 실제 Utility 재검증은 `ORIENT → ANCHOR → EXEMPLIFY → ESCALATE → INTERPRET` 순서의 5-block 계획을 반환했습니다.

2026-08-12 상징적 우화 조합의 Gemma 실검에서는 `ORIENT → ANCHOR → ESCALATE → TURN → STING` 계획, 실제 선택 자료로 제한된 근거 ID, 동일한 종소리 세 번, 상징 비해설, 물리적 이미지 종결을 통과했다. 목표 1,200자에 `max_tokens=2400`을 주어도 803자에서 조기 종료했고 `min_tokens` 강제는 종결문 반복을 만들었으므로 채택하지 않았다. 충분한 근거 두 건과 500자 목표에서는 752자 원고를 정상 저장했고, 초과분을 기계 절단하지 않아 필수 귀결을 보존했다. 임시 프로젝트와 생성물은 검증 후 삭제했다.

Utility 9-case 결과는 Qwen3.5-4B가 namespace 누출로 탈락했고 Gemma4-26B가 88.9%와 격리 gate 통과로 선택됐습니다. source-role 모델 판단은 완전하지 않으므로 애플리케이션의 결정론적 권위 코드가 항상 최종 판정을 합니다.

## 최종 검증

- Ruff PASS
- pytest `48 passed, 3 skipped` (짧은 글 분량 복구·근거 ID 정규화·상징적 우화 자산 계약, 세계관 AI 제안 JSON 복구·자동 재작성·최종 실패 감사 포함; 실제 endpoint opt-in tests는 기본 run에서 skip)
- 실제 모델 opt-in `3 passed` (Writer/Utility, Embedding, Vision)
- bundle/schema/YAML PASS
- Svelte production build PASS
- 실제 데이터 Playwright `46 passed, 12 skipped` (1600×900/390×844/360×844, 현장 구술 전개·문체·결과물 선택, 모바일 자료 본문 scroll·AI 패널·AI 작성 390×500 키보드 가시 높이·command bar·로어북 목차→읽기, 확인·작성 원고 설계·흐름/초안 교체, 원고 저장·완성 다듬기·긴 본문/출처 카드 포함)
- 빈 데이터/기능별 조건 skip UI E2E `28 passed, 30 skipped`
- Compose build/up 및 DB health PASS
- PostgreSQL Alembic `20260810_0008` 기존 데이터 upgrade, 프로젝트 삭제 감사 묘비 보존, 역할별 모델 연결·thinking 설정 및 임시 fresh DB upgrade/downgrade/upgrade PASS
- 프로젝트 로컬 skill package 검증과 UI 계약 정적 preflight `7 passed, 0 failures`

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
