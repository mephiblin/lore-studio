# 로컬 모델 구성

## 역할

- Writer: 장문 초안 작성, 완성본 다듬기와 부분 재작성
- Utility: JSON Schema 구조화, 카드/후보/참고 분석
- Vision: data URL 이미지 캡션과 태그 제안

## 앱에서 연결

`/settings`에서 각 역할의 OpenAI 호환 Base URL과 실제 `/v1/models` alias를 입력하고 `연결 시험` 또는 `시험하고 저장`을 사용합니다. Writer·Utility·Vision은 `이 PC의 로컬 vLLM`에서 Qwen·Gemma·직접 입력을 역할별로 독립 선택할 수 있습니다. 저장값은 `.env`보다 우선하며 `.env로 되돌리기`로 role override만 제거할 수 있습니다. API 키 원문은 브라우저로 다시 반환하지 않습니다.

이 DGX의 로컬 모델 연결은 다음과 같습니다.

| 모델 | 컨테이너용 Base URL | alias | Thinking 기본값 |
|---|---|---|---|
| Qwen3.6 35B heretic MTP | `http://host.docker.internal:18091/v1` | `qwen36-heretic-mtp` | 끄기 |
| Gemma4 26B heretic MTP | `http://host.docker.internal:18093/v1` | `gemma4-26b-heretic-mtp` | 끄기 (vLLM 서버 기본 OFF) |

`이 PC 권장 분담 적용`은 Writer=Gemma, Utility·Vision=Qwen으로 채웁니다. Qwen과 Gemma 모두 vLLM 서버 기본이 `chat_template_kwargs.enable_thinking=false`이며 Lore Studio도 같은 값을 명시적으로 전달합니다. 이 설정은 출력 추론 모드만 끄며 vLLM의 native MTP speculative decoding은 계속 작동합니다. Qwen-MM의 local Faster-Whisper는 별도 도구 서비스이며 Lore Studio의 세 모델 역할에는 포함하지 않습니다.

`세계관 자료 → 자료 양산`과 기존 자료 본문의 `AI 수정 / AI 작성`에서는 역할 재배정과 별개인 `QWEN_SELECTABLE_*`·`GEMMA_SELECTABLE_*` 연결을 모델 이름으로 직접 선택합니다. 선택 모델의 explicit profile로 호출하므로 Qwen 작업 실패 시 Gemma로 자동 fallback하지 않습니다. 자료 양산의 씨앗 제안은 호출 1개이고, 본문 단계는 사용자가 고른 씨앗 1–10개 수만큼 동시 호출합니다.

두 vLLM은 보안을 위해 호스트 loopback에만 바인딩합니다. Qwen은 기존 `qwen-vllm-openwebui-proxy.socket`이 Docker bridge `18091`을 제공합니다. Gemma는 이 저장소의 socket proxy를 한 번 연결하고 활성화합니다.

```bash
systemctl --user link "$PWD/systemd/lore-studio-gemma-vllm-proxy.socket" \
  "$PWD/systemd/lore-studio-gemma-vllm-proxy.service"
systemctl --user enable --now lore-studio-gemma-vllm-proxy.socket
```

이 socket은 `172.17.0.1:18093`만 열고 요청을 `127.0.0.1:18092`로 전달합니다. vLLM 자체를 LAN의 `0.0.0.0`에 공개하지 않습니다.

Compose에서 접근하려면 서버가 Docker bridge에서 접근 가능한 주소에 바인딩되어야 합니다. Lore Studio UI/API는 신뢰 LAN에 공개되지만 모델 포트는 호스트 방화벽으로 LAN 직접 접근을 제한하는 것을 권장합니다. alias는 `/v1/models`의 `id`와 `.env`의 `*_MODEL_NAME`이 정확히 일치해야 합니다. 이미지 입력은 모델과 짝이 맞는 mmproj가 필요합니다.

```bash
make test-models
python scripts/evaluate_utility_model.py --output-dir artifacts/model-evaluation
```

fallback 다운로드는 기본 차단됩니다. 정확한 Hugging Face repo/file을 정하고 크기/SHA256을 검토한 뒤에만 `ALLOW_MODEL_DOWNLOAD=true python scripts/download_fallback_model.py`를 사용하십시오. `.gguf`와 mmproj는 Git에 포함되지 않습니다. 현재 선택과 탈락 사유는 `docs/model-evaluations/`에 기록합니다.

장애 확인 순서는 `/v1/models` → 앱 `/models/status` → alias → host binding → context 크기 → mmproj입니다. 운영 앱에는 가상 모델 fallback이 없으며, endpoint 장애는 UI에 `OFFLINE`과 명시 오류로 드러납니다.
