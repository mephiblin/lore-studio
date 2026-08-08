# 운영

```bash
make dev                 # foreground Compose
make logs                # 앱/DB 로그
make migrate             # Alembic head
make seed                # 재실행 가능한 검은 항로 정식 세계관
make reindex             # 모든 프로젝트 재색인
make backup              # timestamped custom-format dump
make down                # 컨테이너만 종료, volume 유지
```

점검 URL은 `/api/v1/health`, `/api/v1/models/status`, `/api/v1/index/stats?project_id=...`입니다. 모델 status는 alias/capability만 노출하고 endpoint와 API key를 프론트에 보내지 않습니다.

현재 기본 바인딩은 UI `0.0.0.0:5173`, API `0.0.0.0:18000`, PostgreSQL `127.0.0.1:55432`입니다. UI/API는 인증이 없는 신뢰 LAN 전용이며 인터넷 포트 포워딩을 허용하지 않습니다.

장애 시 모델 역할별 상태를 확인합니다. Embedding만 실패하면 FTS로 축소되며 전체 앱은 계속 동작합니다. TTS/ComfyUI 미설정 시 문자 수 기반 예상 길이와 프롬프트 초안만 반환합니다. DB migration 실패 시 앱이 시작되지 않으므로 로그를 확인한 뒤 백업에서 복구하거나 migration을 수정합니다.

NAS는 호스트에서 mount한 뒤 필요한 디렉터리만 read-only로 연결하십시오. DB volume이나 모델 디렉터리를 다른 프로젝트 volume으로 대체하지 마십시오.
