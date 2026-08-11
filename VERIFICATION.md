# 검증 기록

최신 갱신: 2026-08-10
기준 브랜치: `agent/project-taxonomy-and-ui-polish`
환경: DGX Spark, 실제 로컬 모델 endpoint

## 자동 검증

- 역할별 모델 연결: `/settings`와 `model-connections` API로 Writer/Utility/Vision을 `qwen36-heretic-mtp`, Embedding을 기존 `bge-m3`에 연결. key 원문 응답·감사 로그 비노출, `.env` fallback, 저장 전 `/v1/models`/alias 확인, Qwen `enable_thinking=false`와 MTP 독립성 검증 PASS
- 실제 Lore ModelGateway: Writer `연결 성공`, Utility `{"status":"ok"}`, Vision caption/uncertainty 구조화 응답 PASS. `/models/status` 네 역할 `available=true`, Vision image capability와 Embedding 비-chat capability 표시 PASS
- 모델 설정 UI: production build와 Chromium 1600×900·390×844·360×844 집중 회귀 `3 passed, 1 viewport skip`; 5개 생명주기 메뉴 유지, Qwen preset의 Embedding 비변경, API key 재표시 없음, 가로 overflow 없음 PASS
- 모델 설정 DB: 변경 전 `backups/lore-studio-20260810-200130.dump`, 운영 upgrade와 별도 fresh PostgreSQL `upgrade → downgrade 0007 → upgrade` PASS. fresh migration에서 발견한 기존 `0005` index 검사와 신규 migration 멱등성도 보정

- 프로젝트 로컬 `$lore-studio-ui-safety`: skill package 형식 검증 PASS, 기준 문서·5개 생명주기 route와 `/settings` 유틸리티·Alembic head·manifest·API 경유·충돌/디버그 표식 정적 preflight PASS
- `kill-ai-slop` 프론트 점검: 초기 10개 그룹·64개 scanner 후보를 문맥 분류해 정적 `로컬 우선` 광륜 상태 점, 카드·커버·테마 버튼의 위치/크기 hover, 범용 카드의 대형 그림자, 커버 버튼 glass blur, fallback 커버의 다중 그라데이션·동심원, 홈·로어북 중복 eyebrow를 제거. 재스캔 56개는 로어북 열람 테마·서사 본문 serif·실제 순서·상태 표시·modal 레이어로 확인해 의도적 유지. 카드 hover 전후 geometry 불변, fallback `background-image:none`, `.status-dot` 0개 PASS
- de-slop 시각·반응형 회귀: `/`, `/editor`, `/playbook`, `/documents`, `/lorebook`를 1600×900·390×844·360×844에서 실제 데이터로 점검해 가로 overflow 0개·console/page error 0개. 글 만들기 하단 이동 바는 desktop `bottom=888/900`, mobile/narrow `779/844`로 전역 메뉴 위에 유지. 로어북 4개 테마는 실제 click 후 `aria-pressed=true`, 30×30 geometry 불변, `normal/fantasia/mechanical/urban` 로컬 저장·새로고침 유지 PASS
- 프로젝·글 만들기 fallback 커버: 제목을 Unicode 문자 기준 최대 16자로 확장하고 8자를 넘으면 `8자\n나머지`로 표시. 공용 `coverFallbackLabel`·`white-space:pre-line`을 사용하며 긴 임시 프로젝을 생성·검증·삭제하는 desktop/mobile Playwright PASS. 좌측 `로컬 우선` 설명은 DOM에서 제거했고 1600×900·390×844·360×844에서 문구 0개·가로 overflow 0px·커버 비율 1.778·console/page error 0개, 임시 `UX 검증` 프로젝 0개 PASS
- 세계관 자료 AI 수정 422 회귀: Tiptap 전체 선택의 실제 `selection_from=0`과 백엔드·JSON Schema의 최솟값 1 불일치를 재현하고 0을 정상 문서 경계로 수정. 실제 Diablo/두리엘 본문을 Chromium 1600×900에서 전체 선택해 요청한 결과 HTTP 200·`CANDIDATE`·`persisted:false`·저장 본문 불변·가로 overflow 0·console error 0 PASS. 422 표준 검증 상세를 필드별로 표시하고 추가 지시 2,000자·연결 자료 12개·문자열 ID/경계 목록 제한을 프론트에서 선검증. 집중 Playwright desktop/mobile 2 passed
- Ruff: `All checks passed`
- pytest: `33 passed, 3 skipped` (Writer/Utility, Embedding, Vision 실제 endpoint tests는 기본 suite에서 의도적으로 skip)
- 실제 모델 opt-in: `3 passed` (Writer/Utility structured output, BGE-M3 1024차원, Vision data URL)
- SvelteKit adapter-node production build: PASS
- Playwright Chromium desktop 1600×900/mobile 390×844 실제 인수 자료 포함 회귀: `37 passed, 9 skipped`
- 빈 데이터/기능별 조건 skip UI 회귀: `19 passed, 27 skipped`
- 문체·필력: DRAFT 명시 승인·사용 후 새 버전·공용/프로젝트 범위·권리별 짧은 예시 격리 API, 다섯 번째 로컬 탭과 내부 스크롤·고정 footer 모달, 글 만들기 `모델 기본 문체`/승인 프로필 명시 선택, profile/version/example GenerationRun snapshot, 원고 필력 점검과 승인형 수정 제안 PASS
- 프로젝트 전개 방식 생성·수정·글 만들기 선택·삭제 desktop/mobile 집중 회귀: `2 passed`
- 세계관 자료의 전개 방식 목록: 검은 항로/신규 프로젝트 모두 세계관·소설·수필·보고서를 포괄하는 공용 기본 8개 노출, 프로젝트 전용 항목과 출처 구분 PASS
- 전개 방식·자료 종류 카드 갤러리: desktop 카드 폭 305px 이하, mobile 1열, 실제 `required_moves` 순서 표시, 별도 카드 표시·분류 기준 입력 제거, 단계 목적 자동 파생, 생성·수정 모달 접근과 저장 후 자동 닫힘 desktop/mobile PASS
- 새 세계관 자료 생성: 이름·자료 종류만 노출하고 `용도` 선택은 제거, API 기본값 `DRAFT_SETTING` 적용 desktop/mobile PASS
- 집필 지침 세부 규칙 직접 작성: 목표·전개 순서·반드시 포함·피할 전개·선호 결말의 API 저장·카드 표시 desktop/mobile `2 passed`
- 자료 종류·집필 지침·전개 방식 편집: 생성·수정 6개 흐름이 viewport 안의 모달로 열리고 내부 폼만 스크롤되며 고정 footer가 보이는지 desktop/mobile `2 passed`; 집필 지침 세부 규칙은 접기 요소 없이 상시 노출, 도움말은 `position:fixed` 최상위 오버레이로 viewport 안에 표시됨을 확인
- 글 만들기 하단 이동 바: `.playbook-workspace` 밖의 형제 영역이며 desktop viewport 안에 유지되고 mobile에서는 전역 하단 메뉴 위에 고정됨을 확인; 본문·브라우저를 끝까지 스크롤하기 전후 y 좌표가 동일한 desktop/mobile route 회귀 `2 passed`
- 글 만들기 결과물 형태·최종 확인 개편: 세계관·영상·소설·수필·보고서·세계 내부 문서 카드와 실시간 원고 견본, 확인·작성 왼쪽의 동일한 전체 원고 설계 장부, 오른쪽 `글의 흐름 설계 → 초안 작성` 카드와 한 결과 영역을 desktop/mobile 실제 데이터에서 확인. 카드 실행 뒤 같은 영역이 편집 흐름에서 초안으로 교체되고 원고 작업 링크를 제공하며, 자료 경계는 흐름 요청 안에서 자동 컴파일하고 별도 중복 패널을 두지 않음 PASS
- 선택 자료 본문 반영·분량 계약: 직접 고른 자료가 없으면 UI를 비활성화하고 세션·Context compiler 모두 `core`로 강제함을 확인. Planner의 짧게 1,200자·길게 6,500자·직접 지정 5,555자 문단 예산 합계가 목표와 정확히 일치하고, 브라우저 확인 화면에 `총 6,500자 / 목표 6,500자`가 표시됨을 확인
- 결과물 견본 전체 설계 요약: `원고 설계` 장부에 주제·배경·주요 요소·갈등·변수·집필 지침·전개 방식·문체·필력을 실제 선택값 또는 `선택 안 함`으로 표시하고, `출력 설정` 장부의 형식·시점·시제·분량 즉시 갱신과 함께 desktop/mobile 집중 회귀 `2 passed`
- 범용 집필 자산: 소설·수필·보고서 집필 지침 시작 프리셋 3개, 공용 전개 방식 2개 추가, 예시 원문 없는 승인·읽기 전용 문체·필력 3개, 수필·분석 보고서 결과물 형태가 프로젝트와 무관하게 보이고 공용 문체 편집은 복제로만 시작됨을 확인
- 결과물 견본의 `형식 / 시점 / 시제 / 분량` 즉시 요약과 1600×900 viewport 내 전체 노출, 확인 카드의 `수정 → 확인·작성으로 돌아가기`, `수정 취소` 시 기존 선택 복원, 실행 전 완료 녹색 0개·실행 후 순차 완료 상태 PASS
- 저장된 세계관 자료의 기본 읽기 모드·명시적 `글 편집`·저장/취소 복귀, 프로젝트·세계관 자료·로어북 삭제 동작, 로어북 삭제 시 출처 초안 보존·AuditLog PASS
- 73개 자료의 카드 행 비겹침 없음, 독립 스크롤, `자료 더 보기`가 전역 하단 이동 바와 겹치지 않음을 desktop/mobile 숫자·스크린샷으로 확인
- UI 안전성 재감사: 글 만들기 하단 바 77px→61px(상하 padding 18px→10px, 버튼 40px 유지), 문체·필력의 공통 grid 10px 간격·desktop 812px 작업면·독립 스크롤 복구 PASS. mocked API 100개 문체 카드에서 카드 높이 366.5px, list `9475/752px` 내부 스크롤, 폭 300px·행 비겹침을 확인했으며 실제 DB는 변경하지 않음
- 원고 작성 경계 AI 제안: 실제 Utility가 유지 사실 4·공개 유보 2·금지 변경 2개와 근거 구절을 반환, `persisted=false`; 선택 항목만 병합하고 사용자 저장 전 DB 미변경 PASS
- 세계관 자료 AI 본문 편집: 선택 범위 수정·전체/현재 위치/이어쓰기·연결 자료 기본 선택·실행별 참고 자료·CANDIDATE 비교/반영을 desktop/mobile `2 passed`; API는 DB 미변경·GenerationRun·교차 프로젝트 차단·참고 사실 격리 PASS
- AI 수정 문맥·확장 계약: 전체 본문과 선택부 앞뒤 전달, 문맥 요약·연결 조건 필수 응답, `더 자세히 (약 2배)` 최소 길이 JSON Schema와 4,200–8,000 출력 토큰 예산, GenerationRun 프롬프트 버전 기록 PASS. 실제 Gemma Writer에서 `기억세` 120자 선택부가 앞뒤 제도 맥락을 유지한 241자 제안으로 확장됐고 `persisted=false`, 저장 본문 120자 유지 PASS
- AI 수정·AI 작성 제안 본문: 진녹색 `#14322e` 배경과 아이덴티티 금색 `#f0bc65` 텍스트의 계산된 스타일을 desktop/mobile `2 passed`
- 모바일 전개 방식 화면 390×844: 문서/탭 가로 넘침 없음, 네 탭 `nowrap`, browser pageerror 없음 PASS
- 글 만들기·원고 작업 단계 메뉴의 `page-tools` 결합, 글 만들기 본문 외곽 여백 0, 자료 종류 추천 설정 제거를 1600×900/390×844/360×844에서 확인; 가로 넘침·pageerror 없음 PASS
- 원고 작업 3단계 표현 개편: 초안 제목 toolbar 상단 padding 4px·제목/동작 하단 정렬·문단/카드 내부 간격 8px, `재작성 / 문장 점검 / 설정 후보` 단일 활성 원고 도구, 최초 형식·시점·시제·분량·전개·문체를 읽기 전용으로 이어받는 완성 다듬기 기준표, 보강 목표·강도·분량 방향 카드, 항목별 수정 버튼 없는 최종 요약을 실제 데이터 desktop/mobile 확인 PASS. Finalizer는 최신 `editable_draft`와 구조화 `revision_brief`를 기록하며 프론트는 최초 설정을 재전송하지 않음.
- 로어북 로컬 열람 테마: 네 원형 선택기를 책장에서 상단 `.page-tools` 왼쪽으로 이동하고 프로젝트 도구는 오른쪽에 유지, 책장 내부 중복 제거. 밝은 황백색·굵은 적갈색 판타지아, 단순 선형 암부·형광 녹색·8초 간격 배경 글리치 메카니컬, 공포 질감을 제거한 남색 도시 네온 어반 판타지, 이미지보다 어두운 `.workspace-main`, 테마별 `책장` 제목, 네 테마 공통 진녹색·금색 `글 편집`, route 이탈 시 배경 정리를 실제 데이터 desktop/mobile `2 passed`; 1600×900에서는 한 행, 390×844·360×844에서는 테마/프로젝트 두 행이며 가로 overflow 0px·책장 내 테마 toolbar 0개·pageerror 없음 PASS
- 73개 Diablo 자료에서 글 만들기 카드 18개 제한, 모바일 선택 영역 456px, 데스크톱 자료 목록 848px/내부 스크롤, `종족·생물` 필터, 단계 이동 pageerror 없음 PASS
- 매우 길게 실제 분량 복구: `시간의 층위가 머무는 곳: 크리핑 피처(Creeping Feature) 분석 보고서`의 계획 12,000자 대비 기존 초안 3,064자·완성본 2,838자 미달을 재현. `필요한 곳 보강`을 실제 Chromium에서 실행해 36회 OpenAI 호환 Writer 호출·블록별 1,780/1,962/2,861/2,424/2,636/296자, 최종 11,969자(99.7%)를 저장했고 유사 문단 0개·GenerationRun target/actual/call audit를 확인
- 긴 로어북 UI: 위 11,969자 글에서 desktop reader `clientHeight=808`, `scrollHeight=7,577`, `scrollTop 0→500`, provenance가 출처 카드 내부 1개임을 실제 Chromium으로 확인. 읽기/편집·스크롤/출처·네 테마 desktop/mobile 집중 회귀 `6 passed`
- 모바일 UI 재감사: 390×844·360×844 다섯 route에서 세계관 본문의 dead scroll zone을 제거하고 본문 중앙 wheel이 문서 `scrollY`를 이동함을 확인. 360px command bar는 글 만들기 `292→184px`, 원고 작업 `186→134px`, 로어북 목차 `171→122px`; 프로젝트 도구 한 행·가로 overflow 0px PASS
- 모바일 로어북: `/lorebook` 목차 → `?entry=<id>` 독립 읽기 → `← 목차로` 복귀, 직접 URL·새로고침, 11,969자 문서 scroll, 네 테마, 글 편집 왕복 PASS. desktop은 mobile 목차 `display:none`, 책장+본문 grid, reader `808/7,577px` 유지
- 모바일 세계관 AI 패널: 긴 선택 문장으로 편집기가 `3,393.7px`로 늘어나던 min-content 폭과 submit pointer interception을 재현·수정. shell/panel `min-width:0`·sticky review 후 정상 click, AI 수정→반영→AI 작성→반영 실제 Chromium PASS
- 모바일 프로젝트 생성 창 366×758(하단 메뉴 위), 프로젝트 제목 첫 화면 y=408, 로어북 읽기 기본/편집 왕복, 원고 도구 점프 PASS
- 원고 저장 회귀: 제목·문단 수정과 새 문단 추가 → 다음 단계 자동 저장 → 새로고침 복원 → 테스트 데이터 원상복구 PASS
- JSON Schema/YAML/Python bundle validation: PASS
- Docker Compose build/up: DB healthy, backend 18000, frontend 5173
- Alembic PostgreSQL head `20260810_0008`: 기존 데이터 backup 후 upgrade PASS; 프로젝트 삭제 후 `project_id=NULL` 감사 묘비 보존 PASS; 별도 fresh DB에서 전체 upgrade → `20260810_0007` downgrade → head 재-upgrade PASS

## 2026-08-06 실행 상태

- `/api/v1/health`: `status=ok`
- `/api/v1/models/status`: `mode=live`; Writer/Utility/Vision/Embedding 모두 `available=true`
- Compose: DB healthy, backend `18000`, frontend `5173`
- UI 용어: `세계관 자료 / 집필 지침 / 전개 방식 / 결과물 형태 / 초안 / 완성본 / 로어북`으로 통일

## 2026-08-05 실제 모델/DB 인수

- `/models/status`: `mode=live`, Writer/Utility/Vision/Embedding 모두 available; endpoint/key 비노출
- Utility 합성 9건: Qwen3.5-4B FAIL(66.7%, namespace 누출), Gemma4-26B PASS(88.9%, namespace 격리 통과)
- BGE-M3: Compose backend에서 1024차원 1 page/1 chunk 재색인 COMPLETED, Dense 검색으로 `검은 등대` 반환, `dense_error=null`
- Vision: 실제 PNG data URL 분석, caption/objects/tags/uncertainties 반환, `persisted=false`
- Utility: 집필 지침 원문을 유지한 goals/sequence/must/avoid suggestion 반환
- Planner: 근거가 배정된 5문단 글의 흐름 생성
- Writer: 1,039자, 5 LoreBlocks 문서 생성
- 단계: COMPILE_CONTEXT부터 SAVE_REVISION까지 10개 COMPLETED
- GenerationRun: Gemma Utility 3,164 tokens, Writer 3,756 tokens 및 model/runtime/input 기록
- 부분 재작성: 실제 Gemma proposal Diff 생성 후 APPLIED
- 설정 후보: 2개 추출, 사용자 승인 후보는 CANDIDATE→DRAFT_SETTING→PROJECT_CANON 두 승격 로그 기록
- 참고 분석: 실제 Utility가 2개 rhetorical paragraph를 만들고 recipe/Voice Profile 후보를 사용자 승인으로 저장
- SSE: 실제 Writer 호출에서 progress와 complete event 및 저장 문서 반환
- export: Markdown 2,997 bytes, HTML 2,422 bytes, JSON 15,570 bytes

## 검증 경계

실제 외부 TTS와 ComfyUI job 제출은 설정되지 않아 문자 수 예상과 prompt 초안 fallback만 검증했습니다. `playwright-interactive`의 `js_repl`은 현재 세션에 없어, 같은 Playwright Chromium을 일반 runner로 실행해 기능/시각/viewport 검증을 대체했습니다.
