# Utility model real-inference evaluation

Evaluation date: 2026-08-05  
Execution mode: local llama.cpp endpoints, `MODEL_MOCK_ENABLED=false`  
Cases per model: 9 synthetic Korean lore tasks

| Model | Gate | JSON | Semantic | Namespace isolation | Avg. latency | Tokens/s |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3.5-4B-Q4_K_M | **FAIL** | 100% | 66.7% | FAIL | 2.75 s | 28.69 |
| Gemma4-26B-A4B-QAT-Uncensored-HauhauCS-Balanced-MTP-Q4_K_M | **PASS** | 100% | 88.9% | PASS | 2.65 s | 38.83 |

Qwen failed `category_tags`, `source_role`, and the mandatory `namespace_leakage` case. It is therefore not the configured Utility model despite its lower memory cost. Gemma failed only the model-judgment portion of `source_role`; the application enforces source roles and promotion transitions deterministically, so Gemma is selected as the limited Utility fallback.

The selected model is not allowed to create canon, apply reference analysis, or promote candidates by itself. These remain explicit user actions with audit logs. The raw result artifacts are intentionally ignored because they contain complete model responses; the concise, reviewable results are committed in `utility-models.json`.

Vision is not counted as passing in this table. It has a separate live multimodal acceptance check and must not be described as validated until that check succeeds.
