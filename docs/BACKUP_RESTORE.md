# 백업과 복구

`make backup`은 `backups/lore-studio-YYYYMMDD-HHMMSS.dump`를 생성합니다. `backups/`는 Git에서 제외하며 NAS에 복제할 때 파일 권한과 checksum을 함께 보관하십시오.

복구는 대상 DB의 기존 객체를 교체할 수 있는 파괴적 작업입니다. 정확한 Lore Studio 전용 DB와 파일을 확인한 뒤 명시적 확인 문자열을 사용합니다.

```bash
make restore \
  RESTORE_FILE=backups/lore-studio-20260805-120000.dump \
  RESTORE_CONFIRM=restore-lore-studio
make migrate
make reindex
```

먼저 새 임시 DB로 복구해 `lore_app`/`lore_vector` 테이블 수와 대표 문서를 확인하는 것을 권장합니다. 모델 GGUF는 DB 백업에 포함되지 않습니다.
