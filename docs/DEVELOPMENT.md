# 개발

백엔드는 `backend/app`, 프론트는 `frontend/src`, prompt/preset은 `config`, 계약 스키마는 `schema`, migration은 `backend/alembic`에 있습니다.

```bash
make bootstrap
make lint
make test
make build
PLAYWRIGHT_CHROMIUM_PATH=/snap/bin/chromium make e2e
make validate
```

기본 pytest는 SQLite schema translation으로 빠르게 격리하며 PostgreSQL/pgvector와 실제 모델 검증은 명시적 opt-in입니다. migration 변경은 새 revision으로 추가하고 실제 PostgreSQL에서 `upgrade → downgrade → upgrade`를 검증합니다.

모델 호출은 `ModelGateway`, 컨텍스트 권위 경계는 `context_compiler`, 승격은 `authority`, 검색은 `search`, 생성 단계는 `harness`를 거쳐야 합니다. 프론트에서 endpoint/API key를 다루거나 컨셉/방향/레시피/출력 설정을 합친 새 만능 객체를 만들지 마십시오.

CI는 Ruff/pytest, bundle schema/YAML, Svelte build, Compose config, 모델 서비스 미연결 상태의 Playwright UI, secret/large-model guard를 실행합니다. 생성·임베딩 실호출은 DGX에서 `make test-models`로 별도 수행합니다.
