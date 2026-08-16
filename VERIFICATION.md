# 검증 기록

최신 갱신: 2026-08-13
기준 브랜치: `agent/project-taxonomy-and-ui-polish`
환경: DGX Spark, 실제 로컬 모델 endpoint

## 자동 검증

- OpenWebUI Lore Studio 실험 모델 정리: `lore-lab-*` 15개(Qwen 7·Gemma 8)와 `qwen36-diegetic-lore-writer-local` 1개를 정확한 ID 범위로 삭제. 일반 Qwen·Gemma provider와 다른 workspace 모델은 유지하고, 전체 DB와 삭제 행 JSON을 백업. 동기화 명세를 archive로 전환해 명시적 `--restore-archived-labs` 없이는 재등록하지 않음
- 역할별 이중 vLLM 연결: `/settings`와 `model-connections` API로 Writer=`gemma4-26b-heretic-mtp`, Utility/Vision=`qwen36-heretic-mtp`를 등록. key 원문 응답·감사 로그 비노출, `.env` fallback, 저장 전 `/v1/models`/alias 확인, Qwen·Gemma 모두 `enable_thinking=false`와 MTP 독립성 검증 PASS
- Gemma vLLM 서버 기본 Thinking OFF: `chat_template_kwargs`를 보내지 않은 실호출이 `content=OK`, `reasoning_content=null`로 응답. 동일 요청의 MTP 메트릭은 draft 4/accepted 4로 유지 PASS. Lore Studio Writer DB override·Gemma 선택형 profile·설정 UI도 OFF로 일치
- LLM fresh-context 감사: 모든 Writer·Utility·Vision·선택형 호출을 분류하고, `AI 작성`은 현재 본문·작성 경계·명시 선택 참고만 전달. 형식 재시도는 실패 assistant 출력을 제외하고 새로 작성하며, 이어쓰기·품질 수정만 현재 채택 초안을 의도적으로 재사용. 전 생성 호출 `max_tokens` 상한 확인 PASS
- Markdown 편집·읽기: 세계관 자료의 Tiptap↔Markdown 양방향 전환과 AI Markdown 제안 반영, 로어북 `body_markdown` 원문 편집과 제목·강조·목록·인용·코드·링크·구분선 렌더링 PASS. raw HTML은 문자로 표시하고 위험 URL을 링크하지 않음
- 세계관 `AI 작성` 본문 계약: Gemma가 생성한 정상 본문을 JSON 포장 실패로 폐기하던 원인을 제거. 평문·Markdown은 한 번의 text 응답으로 즉시 제안 처리하고 기존 완전 JSON은 호환 해제하며, 빈 응답만 `AI_RESPONSE_EMPTY`로 실패 감사하는 집중 테스트 PASS. 실제 Gemma는 `## 제목 + 두 문단` 평문 Markdown을 반환했고 Lore Studio가 `HTTP 200`, `CANDIDATE`, `persisted=false`로 수용했다. GenerationRun에는 `response_format`·형식 재시도 없이 Thinking OFF와 `max_tokens=900`만 기록됐으며 임시 프로젝트는 삭제 후 404
- 실제 Lore ModelGateway: Gemma Writer가 정확히 `LORE_OK`, Qwen Utility가 `{"status":"ok"}` JSON을 반환하고 Vision image capability를 확인. `/models/status`는 Writer/Utility/Vision 세 역할만 반환 PASS
- Gemma Docker bridge proxy: `lore-studio-gemma-vllm-proxy.socket` active/enabled, `172.17.0.1:18093 → 127.0.0.1:18092`; 실행 중 backend 컨테이너의 `/v1/models`에서 Gemma alias 확인 PASS
- 모델 설정 UI: production build와 Chromium 1600×900·390×844·360×844 집중 회귀 `3 passed, 1 viewport skip`; 실제 운영 화면도 세 viewport 모두 Writer=Gemma·Utility/Vision=Qwen, 로컬 선택기 3개, 가로 overflow 0, console/page error 0 PASS
- 모델 설정 DB: 변경 전 `backups/lore-studio-20260810-200130.dump`, 운영 upgrade와 별도 fresh PostgreSQL `upgrade → downgrade 0007 → upgrade` PASS. fresh migration에서 발견한 기존 `0005` index 검사와 신규 migration 멱등성도 보정
- 세계관 자료 양산: 기본 `Qwen 기획 → Gemma 집필 → 동시 작업 4개`와 접힌 고급 설정, 간단·보통·상세 길이, 씨앗 차별점·참고 근거, 자료 종류별 핵심 항목·계승 사실·새 설정 후보를 구현. 선택 3개·`max_concurrency=2`에서 실제 최대 active worker 2, 부분 실패 시 성공 1·실패 1 분리 보존, accept 전 ConceptPage 불변, 명시 저장 후 `CANDIDATE`, 신뢰된 worker 품질 snapshot 저장, 같은 run 중복 저장 409 PASS. 실제 Qwen은 항구 음식 씨앗 6개를 제안했고, Gemma 3-worker 실행에서 처음 확인된 418자 과소 본문·`candidate_fact` 본문 노출·비정상 JSON을 기준으로 과소 분량/ 내부 표식/구조화 응답 자동 재작성과 첫 완전 JSON 객체 복구를 추가. 최종 실모델 결과는 915자·내부 표식 0·계승 사실 4·새 후보 사실 2, 저장 후 `usage_role=CANDIDATE`·`authority_state=CANDIDATE` PASS. 모의 모델 UI는 1600×900·390×844·360×844에서 기본 경로·접힌 고급 설정·단계 전환·고정 footer·가로 overflow 0 PASS. 실제 검증용 프로젝트는 삭제 후 404, 소속 ConceptPage 0개로 정리됨
- 현장 구술 작성: `세계 내부 구술` Output Profile, `현장 징후에서 경고로` Writing Recipe, `현장 증언 문체` Voice Profile을 분리해 추가. 전용 `max_tokens`·고정 글자 수 없이 기존 분량 계약을 공유하며, 실제 Gemma는 `ORIENT → ANCHOR → EXEMPLIFY → WITHHOLD → ESCALATE → STING` 계획과 1인칭 현장 구술을 생성. 은종의 주인 확정·내부 소제목 노출 없음, 임시 프로젝트 삭제 PASS
- 전체 UI 회귀 중 발견한 기존 경계: Diablo 관계 카드 검사가 최근 수정 자료 순서에 의존하던 것을 관계 있는 `두리엘`의 명시 선택으로 고정. 모바일 로어북의 네 번째 테마 버튼을 우측 고정 모델 설정 링크가 가리던 재현을 확인하고 44px 영역 예약 후 집중 `3 passed, 1 skipped` PASS

- 프로젝트 로컬 `$lore-studio-ui-safety`: skill package 형식 검증 PASS, 기준 문서·5개 생명주기 route와 `/settings` 유틸리티·Alembic head·manifest·API 경유·충돌/디버그 표식 정적 preflight PASS
- `kill-ai-slop` 프론트 점검: 초기 10개 그룹·64개 scanner 후보를 문맥 분류해 정적 `로컬 우선` 광륜 상태 점, 카드·커버·테마 버튼의 위치/크기 hover, 범용 카드의 대형 그림자, 커버 버튼 glass blur, fallback 커버의 다중 그라데이션·동심원, 홈·로어북 중복 eyebrow를 제거. 재스캔 56개는 로어북 열람 테마·서사 본문 serif·실제 순서·상태 표시·modal 레이어로 확인해 의도적 유지. 카드 hover 전후 geometry 불변, fallback `background-image:none`, `.status-dot` 0개 PASS
- de-slop 시각·반응형 회귀: `/`, `/editor`, `/playbook`, `/documents`, `/lorebook`를 1600×900·390×844·360×844에서 실제 데이터로 점검해 가로 overflow 0개·console/page error 0개. 글 만들기 하단 이동 바는 desktop `bottom=888/900`, mobile/narrow `779/844`로 전역 메뉴 위에 유지. 로어북 4개 테마는 실제 click 후 `aria-pressed=true`, 30×30 geometry 불변, `normal/fantasia/mechanical/urban` 로컬 저장·새로고침 유지 PASS
- 프로젝·글 만들기 fallback 커버: 제목을 Unicode 문자 기준 최대 16자로 확장하고 8자를 넘으면 `8자\n나머지`로 표시. 공용 `coverFallbackLabel`·`white-space:pre-line`을 사용하며 긴 임시 프로젝을 생성·검증·삭제하는 desktop/mobile Playwright PASS. 좌측 `로컬 우선` 설명은 DOM에서 제거했고 1600×900·390×844·360×844에서 문구 0개·가로 overflow 0px·커버 비율 1.778·console/page error 0개, 임시 `UX 검증` 프로젝 0개 PASS
- 세계관 자료 AI 수정 422 회귀: Tiptap 전체 선택의 실제 `selection_from=0`과 백엔드·JSON Schema의 최솟값 1 불일치를 재현하고 0을 정상 문서 경계로 수정. 실제 Diablo/두리엘 본문을 Chromium 1600×900에서 전체 선택해 요청한 결과 HTTP 200·`CANDIDATE`·`persisted:false`·저장 본문 불변·가로 overflow 0·console error 0 PASS. 422 표준 검증 상세를 필드별로 표시하고 추가 지시 2,000자·연결 자료 12개·문자열 ID/경계 목록 제한을 프론트에서 선검증. 집중 Playwright desktop/mobile 2 passed
- Ruff: `All checks passed`
- pytest: `51 passed, 2 skipped` (실제 endpoint 두 테스트만 기본 suite에서 의도적으로 skip)
- 실제 모델 opt-in: `2 passed` (Writer/Utility structured output, Vision data URL)
- 임베딩 제거: 모델 설정·gateway·검색/재색인 API·에디터 상태 UI·환경 변수·pgvector 패키지 제거, `20260813_0009`에서 `lore_vector`와 `index_jobs` 및 저장된 역할 설정 삭제. 세계관 자료·원고 행 수 보존 확인
- SvelteKit adapter-node production build 및 backend/frontend 컨테이너 재빌드·재기동, `/api/v1/health` PASS. 자료 양산 집중 Playwright는 desktop/mobile 및 desktop에서 강제한 360px 계약 `3 passed, 1 viewport skip`
- Playwright Chromium 전체 suite: `31 passed, 31 intentional skips`; 모델 설정 집중 `3 passed, 1 skip`, 에디터 양산·AI 편집 집중 `8 passed, 2 skips`
- 세계관 본문 AI 모델 선택: AI 수정에서 Qwen, 이어진 AI 작성에서 Gemma를 선택해 요청 `model_key`와 제안 모델명이 일치하고 desktop/mobile에서 가로 overflow 0 PASS. 실제 요청도 Qwen 수정=`qwen36-heretic-mtp`·`http://host.docker.internal:18091/v1`, Gemma 초안=`gemma4-26b-heretic-mtp`·`http://host.docker.internal:18093/v1`로 GenerationRun에 기록됐으며 둘 다 `CANDIDATE`·`persisted=false`, 원문 불변, 임시 프로젝트 0개로 정리 PASS
- 빈 데이터/기능별 조건 skip UI 회귀: `28 passed, 30 skipped`
- 문체·필력: DRAFT 명시 승인·사용 후 새 버전·공용/프로젝트 범위·권리별 짧은 예시 격리 API, 다섯 번째 로컬 탭과 내부 스크롤·고정 footer 모달, 글 만들기 `모델 기본 문체`/승인 프로필 명시 선택, profile/version/example GenerationRun snapshot, 원고 필력 점검과 승인형 수정 제안 PASS
- 프로젝트 전개 방식 생성·수정·글 만들기 선택·삭제 desktop/mobile 집중 회귀: `2 passed`
- 세계관 자료의 전개 방식 목록: 검은 항로/신규 프로젝트 모두 세계관·소설·수필·보고서·현장 구술을 포괄하는 공용 기본 9개 노출, 프로젝트 전용 항목과 출처 구분 PASS
- 전개 방식·자료 종류 카드 갤러리: desktop 카드 폭 305px 이하, mobile 1열, 실제 `required_moves` 순서 표시, 별도 카드 표시·분류 기준 입력 제거, 단계 목적 자동 파생, 생성·수정 모달 접근과 저장 후 자동 닫힘 desktop/mobile PASS
- 새 세계관 자료 생성: 이름·자료 종류만 노출하고 `용도` 선택은 제거, API 기본값 `DRAFT_SETTING` 적용 desktop/mobile PASS
- 집필 지침 세부 규칙 직접 작성: 목표·전개 순서·반드시 포함·피할 전개·선호 결말의 API 저장·카드 표시 desktop/mobile `2 passed`
- 자료 종류·집필 지침·전개 방식 편집: 생성·수정 6개 흐름이 viewport 안의 모달로 열리고 내부 폼만 스크롤되며 고정 footer가 보이는지 desktop/mobile `2 passed`; 집필 지침 세부 규칙은 접기 요소 없이 상시 노출, 도움말은 `position:fixed` 최상위 오버레이로 viewport 안에 표시됨을 확인
- 글 만들기 하단 이동 바: `.playbook-workspace` 밖의 형제 영역이며 desktop viewport 안에 유지되고 mobile에서는 전역 하단 메뉴 위에 고정됨을 확인; 본문·브라우저를 끝까지 스크롤하기 전후 y 좌표가 동일한 desktop/mobile route 회귀 `2 passed`
- 글 만들기 결과물 형태·최종 확인 개편: 세계관·영상·소설·수필·보고서·세계 내부 문서·세계 내부 구술 카드와 실시간 원고 견본, 확인·작성 왼쪽의 동일한 전체 원고 설계 장부, 오른쪽 `글의 흐름 설계 → 초안 작성` 카드와 한 결과 영역을 desktop/mobile 실제 데이터에서 확인. 카드 실행 뒤 같은 영역이 편집 흐름에서 초안으로 교체되고 원고 작업 링크를 제공하며, 자료 경계는 흐름 요청 안에서 자동 컴파일하고 별도 중복 패널을 두지 않음 PASS
- 선택 자료 본문 반영·분량 계약: 직접 고른 자료가 없으면 UI를 비활성화하고 세션·Context compiler 모두 `core`로 강제함을 확인. Planner의 짧게 1,200자·길게 6,500자·직접 지정 5,555자 문단 예산 합계가 목표와 정확히 일치하고, 브라우저 확인 화면에 `총 6,500자 / 목표 6,500자`가 표시됨을 확인
- 결과물 견본 전체 설계 요약: `원고 설계` 장부에 주제·배경·주요 요소·갈등·변수·집필 지침·전개 방식·문체·필력을 실제 선택값 또는 `선택 안 함`으로 표시하고, `출력 설정` 장부의 형식·시점·시제·분량 즉시 갱신과 함께 desktop/mobile 집중 회귀 `2 passed`
- 범용 집필 자산: 소설·수필·보고서 집필 지침 시작 프리셋 3개, 공용 전개 방식 9개, 예시 원문 없는 승인·읽기 전용 문체·필력 4개, 수필·분석 보고서·세계 내부 구술 결과물 형태가 프로젝트와 무관하게 보이고 공용 문체 편집은 복제로만 시작됨을 확인
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
- 모바일 세계관 `AI 작성`: 390×844에서 참고 자료 목록과 footer가 약 70px 겹치고, 390×500 입력 focus 상태에서 `초안 제안` bottom이 704px로 밀리면서 form `overflow:hidden`으로 접근할 수 없던 실패를 재현. fixed header/footer + 단일 scroll body로 수정한 후 390×844·360×844에서 가로 overflow 0, 390×500에서 body `253/1113px` 스크롤·footer bottom 481px·submit click target PASS. mock API로 실제 제출→Gemma 본문 초안 제안 표시까지 PASS
- 모바일 프로젝트 생성 창 366×758(하단 메뉴 위), 프로젝트 제목 첫 화면 y=408, 로어북 읽기 기본/편집 왕복, 원고 도구 점프 PASS
- 원고 저장 회귀: 제목·문단 수정과 새 문단 추가 → 다음 단계 자동 저장 → 새로고침 복원 → 테스트 데이터 원상복구 PASS
- JSON Schema/YAML/Python bundle validation: PASS
- Docker Compose build/up: DB healthy, backend 18000, frontend 5173
- Alembic PostgreSQL head `20260813_0009`: 기존 데이터 backup 후 upgrade, 제거 대상 스키마·테이블·설정 부재와 원본 자료 보존 확인 PASS

## 2026-08-06 실행 상태

- `/api/v1/health`: `status=ok`
- `/api/v1/models/status`: Writer/Utility/Vision 세 역할만 반환
- Compose: DB healthy, backend `18000`, frontend `5173`
- UI 용어: `세계관 자료 / 집필 지침 / 전개 방식 / 결과물 형태 / 초안 / 완성본 / 로어북`으로 통일

## 2026-08-05 실제 모델/DB 인수

- `/models/status`: `mode=live`, Writer/Utility/Vision 세 역할 available; endpoint/key 비노출
- Utility 합성 9건: Qwen3.5-4B FAIL(66.7%, namespace 누출), Gemma4-26B PASS(88.9%, namespace 격리 통과)
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
