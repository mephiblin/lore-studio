# 로컬 모델 구성

## 역할

- Writer: 장문 계획 기반 집필과 부분 재작성
- Utility: JSON Schema 구조화, 카드/후보/참고 분석
- Vision: data URL 이미지 캡션과 태그 제안
- Embedding: BGE-M3 1024차원 검색 벡터

Writer 라우터 예시:

```bash
llama-server -m /models/writer.gguf --mmproj /models/mmproj.gguf \
  --alias Gemma4-26B --host 0.0.0.0 --port 8080 -c 65536
```

Embedding 예시:

```bash
llama-server -m /models/bge-m3-Q4_K_M.gguf --embedding --pooling cls \
  --alias bge-m3 --host 0.0.0.0 --port 8010 -c 8192
```

Compose에서 접근하려면 서버가 `127.0.0.1`이 아니라 `0.0.0.0`에 바인딩돼야 합니다. Lore Studio UI/API는 신뢰 LAN에 공개되지만 모델 포트 8080/8010은 호스트 방화벽으로 LAN 직접 접근을 제한하는 것을 권장합니다. alias는 `curl http://127.0.0.1:8080/v1/models`의 `id`와 `.env`의 `*_MODEL_NAME`이 정확히 일치해야 합니다. 이미지 입력은 모델과 짝이 맞는 mmproj가 필요합니다.

```bash
make test-models
python scripts/evaluate_utility_model.py --output-dir artifacts/model-evaluation
```

fallback 다운로드는 기본 차단됩니다. 정확한 Hugging Face repo/file을 정하고 크기/SHA256을 검토한 뒤에만 `ALLOW_MODEL_DOWNLOAD=true python scripts/download_fallback_model.py`를 사용하십시오. `.gguf`와 mmproj는 Git에 포함되지 않습니다. 현재 선택과 탈락 사유는 `docs/model-evaluations/`에 기록합니다.

장애 확인 순서는 `/v1/models` → 앱 `/models/status` → alias → host binding → context 크기 → mmproj입니다. 운영에서 `MOCK_MODEL=true`는 장애 격리/오프라인 E2E용이며 실제 품질 검증 결과로 간주하지 않습니다.
