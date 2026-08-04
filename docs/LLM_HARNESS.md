# LLM 하네스

## 역할과 호출

Writer는 최종 원고/부분 재작성, Utility는 Plan과 JSON 구조화, Vision은 이미지, Embedding은 BGE-M3를 담당합니다. 각 역할은 독립 endpoint/alias/timeout/context budget을 가지며 `/v1/models` discovery, retry, JSON object/schema, SSE token streaming, dimension check를 제공합니다. Utility 오류만 명시 설정에서 Writer로 제한 fallback합니다.

## 권위 있는 입력

Context compiler는 프로젝트 scope, namespace, source role, era/continuity를 결정론적으로 검사합니다. 명시 선택 page를 먼저 넣고 locked facts, summaries, passages, open questions, forbidden changes, relations, approved reference analysis, candidate material을 분리합니다. `DISCOURSE_REFERENCE` raw body와 다른 프로젝트 사실은 Writer pack에 들어가지 않습니다.

Planner는 title/angle/blocks(move, purpose, evidence_ids, budget, must/avoid, locked)의 strict JSON Schema를 반환합니다. 사용자가 계획을 수정·저장한 뒤 Writer가 LoreBlock을 생성합니다. Audit는 원고를 자동 수정하지 않고 finding/Diff로만 제안합니다.

모델 장애 시 세션과 입력은 보존되고 구조화 오류는 명시 오류가 됩니다. Embedding 장애는 lexical search로 축소됩니다. 운영 경로는 실제 OpenAI 호환 endpoint만 호출하며 모델이 없거나 응답하지 않으면 성공 응답을 조작하지 않고 명시적으로 실패합니다.

실제 모델 결과와 선택 기준은 `docs/model-evaluations/utility-models.*`와 `VERIFICATION.md`를 참조하십시오.
