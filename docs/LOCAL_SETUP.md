# DGX Spark 로컬 설치

## 요구 환경

Ubuntu ARM64, Docker/Compose, Python 3.12, Node.js 22, `make`가 필요합니다. 모델은 호스트의 llama.cpp OpenAI 호환 서버에서 실행하고 앱/DB는 Compose로 실행하는 구성이 기본입니다.

```bash
git clone https://github.com/mephiblin/lore-studio.git
cd lore-studio
make bootstrap
cp .env.example .env
```

`.env`에서 비밀번호, 실제 model alias, endpoint를 설정합니다. `docker compose config --quiet`로 파싱을 확인한 뒤 실행합니다.

```bash
docker compose up --build
curl http://127.0.0.1:18000/api/v1/health
curl http://127.0.0.1:18000/api/v1/models/status
```

호스트의 8000 포트가 다른 로컬 도구와 충돌하므로 기본 API 포트는 18000입니다. 모든 공개 포트는 `127.0.0.1`에만 바인딩됩니다. NAS 자료는 읽기 전용 bind mount를 별도로 추가하고, 실제 NAS 경로를 Git 추적 파일에 넣지 마십시오.

도구 설치 후 `make test && make lint && make build`를 실행합니다. 기존 DB에는 `make migrate`, 데모에는 `make seed`를 사용합니다.
