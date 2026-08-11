# 보안과 데이터

v1.0은 인증 없는 단일 사용자 로컬 앱입니다. 사용자가 허용한 신뢰 LAN 접속을 위해 Compose의 UI/API는 `0.0.0.0`에 바인딩하지만, PostgreSQL은 `127.0.0.1`에만 유지합니다. 같은 LAN의 다른 사용자도 데이터를 읽고 변경할 수 있으므로 신뢰하는 내부망에서만 사용하십시오. 인터넷 노출에는 이 저장소 범위 밖의 인증 reverse proxy, TLS, 접근 제어와 위협 검토가 필수입니다.

`.env`, API key, 사용자 첨부/원고, DB dump, 모델 파일, 평가 전체 응답, Playwright artifact는 Git에서 제외합니다. 커밋 전 `git status --short`와 CI 대형 파일/비밀 패턴 검사를 확인하십시오.

`/settings`에서 저장한 역할별 API key는 서버의 PostgreSQL `model_connection_settings`에 평문으로 저장되지만 API 응답과 감사 로그에는 원문을 보내지 않고 설정 여부만 반환합니다. 따라서 이 기능은 현재의 단일 사용자·신뢰 LAN 경계 안에서만 사용하십시오. 인터넷 노출이나 다중 사용자 배포 전에 인증, secret 암호화 또는 외부 secret store, key 회전 정책을 먼저 도입해야 합니다.

Qwen·Gemma vLLM 자체는 `127.0.0.1`에만 바인딩합니다. Lore Studio backend 컨테이너는 Docker 기본 bridge의 호스트 주소에만 열린 socket proxy(`18091` Qwen, `18093` Gemma)를 통해 접근하며, 이 proxy를 `0.0.0.0` 또는 LAN 주소에 바인딩하지 않습니다.

삭제는 프로젝트 범위 확인 뒤 명시 API로 수행합니다. 정식 설정 승격, 설정 후보 결정, 재작성 적용은 audit log/revision을 남깁니다. 모델 status API는 endpoint와 credential을 숨깁니다. 이미지 data URL은 Vision 호출에만 전달하며 분석 endpoint는 원본을 자동 저장하지 않습니다.

프롬프트에는 선택한 프로젝트 namespace와 허용 source role만 포함합니다. `DISCOURSE_REFERENCE` 원문은 Writer 사실 pack에서 제거하고 승인된 구조 분석만 사용합니다. 자동 모델 다운로드는 opt-in이며 크기/SHA256 검증을 지원합니다.
