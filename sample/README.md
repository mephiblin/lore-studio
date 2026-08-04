# 샘플 자료

이 폴더는 특정 상용 IP를 복제하지 않는 원본 예시 세계관을 사용합니다.

- `concept-pages/`: 컨셉 페이지 본문의 예시
- `direction-card.yaml`: 재사용 가능한 방향성 카드
- `playbook-request.json`: API로 플레이북 세션을 만드는 예시

실제 DB에 정식 검은 항로 세계관을 적재하려면 루트에서 다음을 실행하십시오.

```bash
python scripts/seed_world.py --generate
```
