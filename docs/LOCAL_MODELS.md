# 로컬 모델 구성

## 역할

- Writer: 장문 초안 작성, 완성본 다듬기와 부분 재작성
- Utility: JSON Schema 구조화, 카드/후보/참고 분석
- Vision: data URL 이미지 캡션과 태그 제안
- Embedding: BGE-M3 1024차원 검색 벡터

## 앱에서 연결

`/settings`에서 각 역할의 OpenAI 호환 Base URL과 실제 `/v1/models` alias를 입력하고 `연결 시험` 또는 `시험하고 저장`을 사용합니다. 저장값은 `.env`보다 우선하며 `.env로 되돌리기`로 role override만 제거할 수 있습니다. API 키 원문은 브라우저로 다시 반환하지 않습니다.

이 DGX의 로컬 Qwen3.6 vLLM은 컨테이너에서 `http://host.docker.internal:18091/v1`, alias `qwen36-heretic-mtp`, API key `EMPTY`로 접근합니다. `이 PC의 Qwen 값 채우기`는 Writer·Utility·Vision만 채우고 BGE-M3 Embedding은 유지하며 `Thinking 끄기`를 선택해 짧은 구조화 응답의 숨은 추론 토큰을 줄입니다. 이 설정은 `chat_template_kwargs.enable_thinking=false`이고 vLLM의 native MTP speculative decoding은 계속 작동합니다. Qwen-MM의 local Faster-Whisper는 별도 도구 서비스이며 Lore Studio의 네 모델 역할에는 포함하지 않습니다.

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
EMBEDDING_BASE_URL=http://127.0.0.1:8010/v1 make test-models
python scripts/evaluate_utility_model.py --output-dir artifacts/model-evaluation
```

fallback 다운로드는 기본 차단됩니다. 정확한 Hugging Face repo/file을 정하고 크기/SHA256을 검토한 뒤에만 `ALLOW_MODEL_DOWNLOAD=true python scripts/download_fallback_model.py`를 사용하십시오. `.gguf`와 mmproj는 Git에 포함되지 않습니다. 현재 선택과 탈락 사유는 `docs/model-evaluations/`에 기록합니다.

장애 확인 순서는 `/v1/models` → 앱 `/models/status` → alias → host binding → context 크기 → mmproj입니다. 운영 앱에는 가상 모델 fallback이 없으며, endpoint 장애는 UI에 `OFFLINE`과 명시 오류로 드러납니다.
