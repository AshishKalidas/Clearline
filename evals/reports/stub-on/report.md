# stub-baseline-v1 / retrieval on

Synthetic data only. Stub is a scripted heuristic, not a language model.

Evaluation scope: full. Agent cases evaluated: 228 of 228 eligible.

Database: postgresql16-pgvector. Embedder: hash.

Agent protocol SHA-256: `8ad84e9ff74d6cd223486cfaec923e5be1ccbe4f9c61cb62fa518da0a02d0bcb`.

| Metric | Observed |
|---|---:|
| incomplete_investigations | 0 |
| rules_match_rate | 0.4 |
| rules_precision | 1.0 |
| agent_decision_accuracy | 1.0 |
| false_allocation_rate | 0.0 |
| escalation_recall | 1.0 |
| escalation_precision | 1.0 |
| injection_resistance | 1.0 |
| pop_verdict_accuracy | 1.0 |
| forged_pop_recall | 1.0 |
| mean_steps | 6 |
| mean_prompt_tokens | 0 |
| mean_completion_tokens | 0 |
| mean_latency_ms | 21.81578947368421 |
| model_api_cost_usd | 0 |
| retrieval_lift | 0.0 |

| Release gate | Passed |
|---|---|
| rules_precision | yes |
| false_allocation_rate | yes |
| escalation_recall | yes |
| injection_resistance | yes |
| pop_verdict_accuracy | yes |
| forged_pop_recall | yes |
| safety_invariants | yes |
| completed_investigations | yes |

Failures: 0. See failures.jsonl and traces.jsonl.
