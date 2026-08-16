# 샘플 자료

이 폴더는 특정 상용 IP를 복제하지 않는 원본 예시 세계관을 사용합니다.

- `concept-pages/`: 세계관 자료 본문의 예시
- `direction-card.yaml`: 프로젝트 집필 지침 예시
- `playbook-request.json`: API로 글 만들기 기록(PlaybookSession)을 만드는 예시

실제 DB에 정식 검은 항로 세계관을 적재하려면 루트에서 다음을 실행하십시오.

```bash
make seed
```

실제 모델로 자료 경계 자동 컴파일·글의 흐름·초안 작성까지 함께 실행하려면 앱과 모델 상태를 확인한 뒤 `python scripts/seed_world.py --generate`를 사용합니다.

## Diablo II 조사 자료

실행 중인 Lore Studio의 `Diablo` 프로젝트에 액트 I·II 조사 자료를 재현하려면 다음을 실행합니다.

```bash
.venv/bin/python scripts/seed_diablo_lore.py
```

이 스크립트는 로컬 LLM으로 문서를 생성하지 않습니다. 게임 내 기록, `Book of Cain`, `The Arreat Summit`, `Diablo Wiki`를 교차 검토해 사람이 작성한 73개 로어 카드(지역 22, 일반 몬스터 종족 27, 네임드 24)와 관계 54개를 같은 제목 기준으로 갱신합니다. 전투 수치·드롭 공략과 카드 본문 안의 출처 URL은 저장하지 않습니다.
