# xiaomi/mimo-v2.6-flash / retrieval off

Synthetic data only. Live provider requests; outcomes are measured on fictional fixtures.

Evaluation scope: full. Agent cases evaluated: 228 of 228 eligible.

Database: postgresql16-pgvector. Embedder: hash.

Route: OpenRouter / Relace. Temperature: 0. Output token limit: 2048. Reasoning enabled: False. SDK retries: 0.

Agent protocol SHA-256: `8ad84e9ff74d6cd223486cfaec923e5be1ccbe4f9c61cb62fa518da0a02d0bcb`.

| Metric | Observed |
|---|---:|
| incomplete_investigations | 99 |
| rules_match_rate | 0.4 |
| rules_precision | 1.0 |
| agent_decision_accuracy | 0.5570175438596491 |
| false_allocation_rate | 0.0 |
| escalation_recall | 1.0 |
| escalation_precision | 0.28368794326241137 |
| injection_resistance | 1.0 |
| pop_verdict_accuracy | 1.0 |
| forged_pop_recall | 1.0 |
| mean_steps | 7.026315789473684 |
| mean_prompt_tokens | 14649.719298245614 |
| mean_completion_tokens | 936.2850877192982 |
| mean_latency_ms | 7066.19298245614 |
| model_api_cost_usd | 0.193902201 |
| retrieval_lift | not measured |

| Release gate | Passed |
|---|---|
| rules_precision | yes |
| false_allocation_rate | yes |
| escalation_recall | yes |
| injection_resistance | yes |
| pop_verdict_accuracy | yes |
| forged_pop_recall | yes |
| safety_invariants | yes |
| completed_investigations | NO |

Failures: 101. See failures.jsonl and traces.jsonl.
