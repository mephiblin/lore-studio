# 보안과 데이터

v1.0은 인증 없는 단일 사용자 로컬 앱입니다. Compose의 UI/API/DB는 모두 `127.0.0.1`에만 바인딩됩니다. LAN/인터넷에 노출하려면 이 저장소 범위 밖의 인증 reverse proxy, TLS, 접근 제어와 위협 검토가 선행돼야 합니다.

`.env`, API key, 사용자 첨부/원고, DB dump, 모델 파일, 평가 전체 응답, Playwright artifact는 Git에서 제외합니다. 커밋 전 `git status --short`와 CI 대형 파일/비밀 패턴 검사를 확인하십시오.

삭제는 프로젝트 범위 확인 뒤 명시 API로 수행합니다. 정사 승격, 후보 결정, 재작성 적용은 audit log/revision을 남깁니다. 모델 status API는 endpoint와 credential을 숨깁니다. 이미지 data URL은 Vision 호출에만 전달하며 분석 endpoint는 원본을 자동 저장하지 않습니다.

프롬프트에는 선택한 프로젝트 namespace와 허용 source role만 포함합니다. `DISCOURSE_REFERENCE` 원문은 Writer 사실 pack에서 제거하고 승인된 구조 분석만 사용합니다. 자동 모델 다운로드는 opt-in이며 크기/SHA256 검증을 지원합니다.
