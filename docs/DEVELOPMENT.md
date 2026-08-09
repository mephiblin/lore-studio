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

현재 migration head는 `20260809_0006`이고, 기본 검증 기준은 pytest `23 passed, 3 skipped`, 빈 데이터에서도 실행되는 Playwright `19 passed, 19 skipped`입니다. 프로젝트 전개 방식 CRUD·글 만들기 연결과 다량 설정 카드의 높이·내부 스크롤 회귀는 이 기본 실행에 포함되며, 검은 항로 인수 자료가 필요한 시나리오는 `E2E_EXPECT_DATA=true`에서 별도 실행합니다. `make seed`는 예제 세계관을 적재하지만 특정 `video_narration` 초안까지 보장하지 않으므로 전체 인수 테스트의 선행 조건과 같지 않습니다. 수치는 기능 변경 때 `VERIFICATION.md`와 `docs/IMPLEMENTATION_STATUS.md`에 함께 갱신합니다.

모델 호출은 `ModelGateway`, 컨텍스트 권위 경계는 `context_compiler`, 승격은 `authority`, 검색은 `search`, 생성 단계는 `harness`를 거쳐야 합니다. 프론트에서 endpoint/API key를 다루거나 컨셉/방향/레시피/출력 설정을 합친 새 만능 객체를 만들지 마십시오.

CI는 Ruff/pytest, bundle schema/YAML, Svelte build, Compose config, 모델 서비스 미연결 상태의 Playwright UI, secret/large-model guard를 실행합니다. 생성·임베딩 실호출은 DGX에서 `make test-models`로 별도 수행합니다.

기능 변경 완료 전에는 [`CHANGE_SAFETY_CHECKLIST.md`](CHANGE_SAFETY_CHECKLIST.md)로 코드 상태, 취소·저장 흐름, 삭제 경계, 고아 UI, 반응형 레이아웃, 문서 일치를 확인합니다.

UI·페이지 점검과 사용자에게 보이는 기능 변경에는 project-local skill [`lore-studio-ui-safety`](../.codex/skills/lore-studio-ui-safety/SKILL.md)를 사용합니다. `$lore-studio-ui-safety`로 명시 호출할 수 있으며, 시작 시 `python3 .codex/skills/lore-studio-ui-safety/scripts/check_contract_sync.py`로 기준 문서·route·migration·manifest·API 경유 규칙을 검사합니다.
