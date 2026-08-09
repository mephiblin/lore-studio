# v1.0 인수 결과

| # | 조건 | 결과 | 증거 |
|---:|---|---|---|
| 1 | Compose build/up | PASS | DB healthy, API 18000, UI 5173 |
| 2 | 프로젝트 생성 | PASS | 실제 API/UI 프로젝트 |
| 3 | 자유 본문 저장 | PASS | API integration + Tiptap UI |
| 4 | 프로젝트별 자료 종류/태그/역할/관계 검색 | PASS | 카드형 종류 생성·이름 수정·필터, 별도 분류 기준 제거, 다른 프로젝트 종류 연결 차단, 사용 중 삭제 차단, 이름 기반 연결/역연결 |
| 5 | 프로젝트 집필 지침 다중 조합 | PASS | 카드형 선택, 목적 설명, 충돌 경고 |
| 6 | 자료 역할 선택 | PASS | 한 단계에 한 역할만 노출, 전체 미배정 자료 18개·더 보기, 검색·종류 필터, 중복 역할 방지, 선택 단계 건너뛰기 |
| 7 | 선택/설정/seed 재현 | PASS | 생성 세션에 모든 선택과 seed 저장 |
| 8 | 공용·프로젝트 전개 방식/결과물/시점·시제/분량/범위/자유도 | PASS | 소설·수필·보고서 공용 자산, 프로젝트 전개 방식 CRUD·격리, 실제 `required_moves` 카드 순서, 선택 분량과 문단 예산 합계 일치 |
| 9 | 사실/질문/금지/참고 구분 | PASS | 글의 흐름 생성 시 자동 컴파일하며 별도 실행 단계 없이 최종 원고 설계 카드에 경계와 경고 표시 |
| 10 | editable plan | PASS | 실제 Gemma 5 blocks + 최종 확인 화면에 바로 열리는 ‘글의 흐름’ 편집 카드 |
| 11 | Gemma Writer 전체 원고 | PASS | 1,039자/5 blocks |
| 12 | 검증된 Utility | PASS | Gemma pass, Qwen reject |
| 13 | BGE-M3 검색 | PASS | 실제 Compose Dense hit |
| 14 | 임베딩 저장소 격리 | PASS | lore_studio_pgdata/lore_vector |
| 15 | LoreBlock 저장 | PASS | 제목·상태·전체 문단 원자 저장, 문단 추가/수정/삭제, 단계 이동 자동 저장과 새로고침 복원, 모바일 편집 UI |
| 16 | 부분 재작성 Diff 승인/취소 | PASS | real proposal/apply + dismiss API/UI, 모바일 원고 도구 점프와 결과 자동 이동 |
| 17 | 근거와 감사 | PASS | UUID 대신 자료명 근거 chip + 3 auditors |
| 18 | 정식 설정 자동 승격 금지 | PASS | invariant/API test |
| 19 | 후보 추출/승인 | PASS | real extraction/two-step audit |
| 20 | 참고 구조 분석·사실 격리 | PASS | raw body excluded + leakage tests |
| 21 | MD/HTML/JSON export | PASS | 실제 byte 결과 |
| 22 | 모델 서비스 미연결 UI E2E | PASS | 성공 응답 조작 없이 OFFLINE 상태와 반응형 UI 검증 |
| 23 | 실제 Writer/Utility/Embedding 결과 | PASS | `VERIFICATION.md`/evaluation JSON |
| 24 | migration/tests | PASS | PostgreSQL up/down/up, pytest/build/e2e |
| 25 | 상태 문서 일치 | PASS | README/TASKS/status/audit updated |
| 26 | 초안 전체를 완성본으로 통합 | PASS | 원본 설계 상속, 구조화 보강 지시, `FINAL_COHERENCE_PASS`, 초안과 로어북 문서 분리, 출처 해시 변경 감지 |
| 27 | 로어북 독립 탐색 | PASS | 상단 로어북 메뉴, 기본 읽기/명시적 편집 모드, 줄바꿈 제목, 내보내기, 출처 초안 이동 |
| 28 | 세계관 자료 AI 본문 편집 | PASS | 선택 범위 문맥 수정, 실행별 참고 자료 선택, CANDIDATE 비교·반영, DB 자동 저장 금지, 교차 프로젝트·참고 사실 격리 |
| 29 | 문체 프로필 수명주기·격리 | PASS | DRAFT 명시 승인, 사용 후 새 버전, 공용/프로젝트 범위, 사용 기록 삭제 차단, 권리별 예시 격리 API test |
| 30 | 문체·필력 생성 연결 | PASS | 글 만들기 명시 선택, Context compiler의 비사실 expression/style pack, Writer·Finalizer·부분 재작성 snapshot |
| 31 | 필력 점검과 사용자 승인 | PASS | 원고 해시 gate, 결정론·Utility finding, 항목별 REWRITE 제안, 명시 apply 전 원고 불변 |
| 32 | 확인 수정 복귀·순차 진행 | PASS | 왼쪽 전체 원고 설계 유지, 소재·집필 원칙·표현 설계 수정 후 확인·작성 복귀, 오른쪽 동일 영역의 흐름→초안 교체와 실행별 완료 색상 |
| 33 | 저장 자료 읽기 모드·안전 삭제 | PASS | 세계관 자료 글 편집 gate, 프로젝트·자료·로어북 명시 확인 삭제, 출처 초안 보존·AuditLog |
| 34 | 대규모 자료 하단 동작 | PASS | 73개 카드 행 비겹침 방지·독립 스크롤, `자료 더 보기`와 전역 하단 바 desktop/mobile 비겹침 |
| 35 | 페이지 UI 안전성 재감사 | PASS | 글 만들기 footer 수직 밀도, 문체·필력 공통 작업면 간격·높이·스크롤, 100개 설정 카드 높이 보존, 3개 viewport 고아·overflow 검사 |
| 36 | 프로젝트 로컬 UI 안전 점검 | PASS | `$lore-studio-ui-safety`가 UI 계약·변경 체크리스트를 로드하고 route·migration·manifest·API 경유 정적 preflight를 실행하며 변경 유형별 문서·테스트 동기화 범위를 지정 |
| 37 | 원고 작업 3단계 시각 단순화 | PASS | 콤팩트 제목·동작 정렬, 8px 문단 간격, 단일 활성 원고 도구, 읽기 전용 초안 설계·보강 카드형 완성 다듬기, 수정 버튼 없는 최종 요약, 390px·360px 단계 전환 상단 복귀 |
| 38 | 로어북 로컬 열람 테마 | PASS | `.page-tools` 왼쪽 배치·책장 비중복, 밝은 양피지·형광 CRT 글리치·남색 도시 네온 역할, 어두운 작업면 여백, 공통 편집 버튼, 전환/새로고침 유지, 읽기·편집 대비, 본문·내보내기 불변, desktop/mobile/narrow overflow 검사 |
| 39 | 범용 글 구성·분량 계약 | PASS | 소설·수필·분석 보고서용 프리셋과 결과물·문체 프로필, 자료 미선택 시 본문 범위 자동 축소, 짧게·길게·직접 지정 분량과 계획 예산 합계 일치 |
| 40 | 결과물 견본의 전체 원고 설계 | PASS | 주제·배경·주요 요소·갈등·변수·집필 지침·전개 방식·문체·필력을 원고 설계 장부에 표시하고 형식·시점·시제·분량 출력 장부와 분리, desktop/mobile 일치 |

대표 실제 프로젝트 slug는 `black-route-chronicle`이며 로컬 전용 DB에 정식 세계관 자료 9개와 관계·집필 지침을 보관합니다. 기본 전개 방식 프리셋은 공용이고, 사용자가 만든 전개 방식과 참고 분석 승인 결과는 프로젝트에 귀속됩니다. 최신 자동 검증 수치는 루트 `VERIFICATION.md`를 권위 기록으로 사용합니다.
