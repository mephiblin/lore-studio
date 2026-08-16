# LLM 하네스

## 역할과 호출

Writer는 초안 작성·완성본 다듬기·부분 재작성, Utility는 글의 흐름과 JSON 구조화, Vision은 이미지를 담당합니다. 각 역할은 독립 endpoint/alias/timeout/context budget을 가지며 `/v1/models` discovery, retry, JSON object/schema, SSE token streaming을 제공합니다. Utility 오류만 명시 설정에서 Writer로 제한 fallback합니다.

## 권위 있는 입력

Context compiler는 프로젝트 scope, namespace, source role을 결정론적으로 검사합니다. 글의 흐름 생성 시 자동 실행되어 명시 선택 page를 먼저 넣고 locked facts, summaries, passages, open questions, forbidden changes, relations, approved reference analysis, candidate material을 분리합니다. `DISCOURSE_REFERENCE` raw body와 다른 프로젝트 사실은 Writer pack에 들어가지 않습니다. `context_depth`는 이미 선택한 자료의 자유 본문 포함량만 바꾸며, 선택 자료가 없으면 `core`로 고정됩니다.

Planner는 title/angle/blocks(move, purpose, evidence_ids, budget, must/avoid, locked)의 strict JSON Schema를 반환합니다. 서버는 `짧게/보통/길게/매우 길게/직접 지정`을 목표 문자 수로 해석하고 모든 문단 예산 합계를 그 목표와 정확히 맞춥니다. 6,000자 이상 장문은 단일 응답의 종료 시점에 분량을 맡기지 않고 전개 블록별 새 구간을 이어 씁니다. 결과물 형태에 따라 소설은 행동·감각·갈등, 수필은 경험·관점 변화·성찰, 설명·보고서는 근거·인과·한계 초점을 순환합니다. 각 호출 뒤 실제 한국어 글자 수를 측정하고, 자연스럽게 짧게 닫힌 결론의 예산은 앞선 전개 구간으로 재배분합니다. 구간별 편차는 허용하되 전체 목표의 95%를 채우며, 계획 대비 가장 부족한 구간부터 보충합니다. 같은 문단의 재출력과 유사한 바꿔쓰기는 생성 중·저장 직전 두 번 제거하고, 목표·실제 글자 수·호출 수·블록별 결과를 GenerationRun에 기록합니다. 전체 분량 또는 중복 gate를 통과하지 못한 결과는 저장하지 않고 명시 오류로 남깁니다. 사용자가 글의 흐름을 수정·저장한 뒤 Writer가 LoreBlock 초안을 생성합니다. 초안 편집 뒤 Finalizer는 최신 LoreBlock 전체와 원래 생성 설계를 그대로 받고, 사용자가 고른 `revision_brief`의 보강 목표·강도·분량 방향 안에서 `FINAL_COHERENCE_PASS`를 실행해 별도 로어북 문서를 저장합니다. `필요한 곳 보강`은 현재 초안이 원래 선택 분량에 못 미치면 그 목표까지 복구하며, 새 사실 대신 기존 사실의 연결·장면·근거·한계를 확장합니다. Audit는 초안을 자동 수정하지 않고 finding/Diff로만 제안합니다.

6,000자 미만은 목표 글자 수에서 계산한 `max_tokens` 안전 상한을 사용하되, 모델이 일찍 종료해 95%에 미달하면 결말 뒤에 억지로 이어 쓰지 않고 마지막 문단 직전에 새 사실 없이 계획의 아직 부족한 장면·반응·인과·이행만 최대 세 번 삽입합니다. 이 복구 뒤에도 95%에 못 미친 초안과 완성본은 저장하지 않습니다.

`SamplingProfile`은 분량이나 글의 의미를 소유하지 않는 별도 런타임 계층입니다. Writer는 선택한 `temperature/top_p/top_k/frequency_penalty/presence_penalty`를 사용하고, Planner는 strict JSON 안정성을 위해 기존 고정 온도를 유지합니다. Finalizer는 선택값을 그대로 증폭하지 않고 temperature 0.48, top-p 0.86, top-k 32 상한으로 파생합니다. 선택 key·version·override가 반영된 실제 값은 Context pack, 원고 생성 입력, GenerationRun에 함께 저장합니다. 호출별 `max_tokens`는 목표를 강제하는 값이 아니라 모델이 낼 수 있는 최대 토큰 수를 막는 안전 상한이며 사용자 카드 설정이 아닙니다. 실제 분량 충족 여부는 한국어 글자 수를 재어 판정합니다.

모델 장애 시 세션과 입력은 보존되고 구조화 오류는 명시 오류가 됩니다. 운영 경로는 실제 OpenAI 호환 endpoint만 호출하며 모델이 없거나 응답하지 않으면 성공 응답을 조작하지 않고 명시적으로 실패합니다.

## 호출별 새 문맥 규칙

Lore Studio의 생성 호출은 대화 세션을 재사용하지 않고 각 요청이 전달한 `messages`만으로 독립 실행됩니다. vLLM prefix/KV cache는 같은 입력의 계산을 재사용할 뿐 이전 대화나 생각을 새 요청에 암묵적으로 넣지 않습니다.

| 호출 | 새 요청에 포함하는 문맥 | 이전 AI 출력 처리 |
|---|---|---|
| Planner·Utility 분석 | 현재 작업 스냅샷과 구조화 계약 | 포함하지 않음 |
| 세계관 본문 `AI 작성` | 사용자 지시, 현재 본문, 작성 경계, 명시 선택 참고 자료 | 포함하지 않음. 형식 재시도도 실패 출력 없이 처음부터 새로 작성 |
| 선택 영역·문단 재작성 | 현재 대상, 앞뒤 문맥, 사실·문체 경계 | 포함하지 않음 |
| 자료 양산 씨앗·worker | 고정된 참고 스냅샷, 선택 씨앗, 자료 종류 | 품질 보정이 필요한 현재 후보만 의도적으로 포함; 형식 실패 출력은 제외 |
| 장문 초안·Finalizer | 현재 계획, 근거, 사용자가 수정·수용한 최신 초안 | 이어쓰기·보정 대상인 수용 본문만 의도적으로 포함 |
| Vision | 현재 이미지와 분석 지시 | 포함하지 않음 |

모든 로컬 생성 호출은 Thinking OFF를 기본으로 하며, 각 호출은 작업 분량과 복구 여유에 맞는 `max_tokens` 안전 상한을 명시합니다. 이 상한은 목표 글자 수가 아니며 실제 분량은 글자 수 계약으로 별도 검증합니다.

실제 모델 결과와 선택 기준은 `docs/model-evaluations/utility-models.*`와 `VERIFICATION.md`를 참조하십시오.

VoiceProfile은 별도 `expression_design`으로 컴파일하며, 권리·상태가 허용된 짧은 예시만 독립 토큰 예산 안에서 `style_examples`에 넣습니다. 이 입력은 사실 근거가 아니며 결과물 형태와 시점·시제가 항상 우선합니다. Planner의 문단에는 `scene_mode`와 `expression_focus`가 추가됩니다. 초안·Finalizer·부분 재작성은 같은 voice snapshot을 사용합니다. 필력 점검은 결정론적 검사와 Utility 감사를 합치지만, 사용자가 항목별 Writer 수정안을 승인하기 전에는 원고를 바꾸지 않습니다.
