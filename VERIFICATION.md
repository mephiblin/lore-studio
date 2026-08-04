# 검증 기록

## 완료된 검증

- `backend/app` 및 테스트 파일 Python 컴파일 성공
- 백엔드 단위 테스트: `3 passed`
- 임시 SQLite DB를 사용한 API 스모크 테스트 성공
  - 프로젝트 생성
  - 컨셉 페이지 생성
  - 집필 레시피 시드
  - 플레이북 세션 생성
  - 컨텍스트 미리보기
  - 구성안 생성
  - Mock 로어 문서 생성 및 저장
- 모든 JSON Schema 파싱 성공
- 모든 YAML 설정 파일 파싱 성공
- `frontend/package.json` JSON 검증 성공
- 통합 DOCX 19쪽 렌더링 및 페이지별 시각 검수 완료

## 이 실행 환경에서 완료하지 못한 검증

- 프론트엔드 `npm install`과 SvelteKit 빌드: 현재 컨테이너의 내부 npm 레지스트리에 SvelteKit/Tiptap 패키지가 제공되지 않아 설치 단계에서 중단됨. 소스와 패키지 명세는 포함되어 있으며, 일반 npm 레지스트리에 접근 가능한 환경에서 빌드해야 한다.
- Docker Compose 실제 기동: 현재 컨테이너에 Docker CLI가 설치되어 있지 않아 실행하지 못함.

## 권장 첫 실행 확인

```bash
cp .env.example .env
docker compose up --build
python scripts/seed_demo.py --generate
```

UI에서 프로젝트, 컨셉 페이지, 방향성 카드, 플레이북, 로어 문서가 생성되는지 확인한다.
