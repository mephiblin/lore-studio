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

현재 migration head는 `20260810_0008`입니다. 역할별 모델 연결 변경은 설정 API 단위 테스트, `/settings`의 desktop 1600×900·mobile 390×844·narrow 360×844 Playwright, 실제 PostgreSQL migration으로 함께 검증합니다. 전체 suite 수치는 기능 변경 때 `VERIFICATION.md`와 `docs/IMPLEMENTATION_STATUS.md`에 함께 갱신합니다. 검은 항로 인수 자료가 필요한 시나리오는 `E2E_EXPECT_DATA=true`에서 별도 실행하며, `make seed`는 예제 세계관을 적재하지만 특정 `video_narration` 초안까지 보장하지 않습니다.

모델 호출은 `ModelGateway`, 컨텍스트 권위 경계는 `context_compiler`, 승격은 `authority`, 검색은 `search`, 생성 단계는 `harness`를 거쳐야 합니다. 모델 endpoint/API key 편집은 `/settings`와 `model-connections` API에만 두고, 키 원문을 응답·감사 로그에 반환하지 마십시오. 컨셉/방향/레시피/출력 설정을 합친 새 만능 객체를 만들지 마십시오.

자료 양산은 `concept_batch` 서비스와 `/concept-batches/seeds → /generate → /accept` 계약을 사용합니다. planning은 단일 explicit model profile, worker는 선택 씨앗마다 병렬 호출하며, API 테스트는 실제 최대 active 호출 수와 accept 전 ConceptPage 불변을 함께 검증해야 합니다.

CI는 Ruff/pytest, bundle schema/YAML, Svelte build, Compose config, 모델 서비스 미연결 상태의 Playwright UI, secret/large-model guard를 실행합니다. 생성·임베딩 실호출은 DGX에서 `make test-models`로 별도 수행합니다.

기능 변경 완료 전에는 [`CHANGE_SAFETY_CHECKLIST.md`](CHANGE_SAFETY_CHECKLIST.md)로 코드 상태, 취소·저장 흐름, 삭제 경계, 고아 UI, 반응형 레이아웃, 문서 일치를 확인합니다.

UI·페이지 점검과 사용자에게 보이는 기능 변경에는 project-local skill [`lore-studio-ui-safety`](../.codex/skills/lore-studio-ui-safety/SKILL.md)를 사용합니다. `$lore-studio-ui-safety`로 명시 호출할 수 있으며, 시작 시 `python3 .codex/skills/lore-studio-ui-safety/scripts/check_contract_sync.py`로 기준 문서·route·migration·manifest·API 경유 규칙을 검사합니다.
