# xiaomi/mimo-v2.6-flash / retrieval on

Synthetic data only. Live provider requests; outcomes are measured on fictional fixtures.

Evaluation scope: pilot. Agent cases evaluated: 20 of 228 eligible.

Database: postgresql16-pgvector. Embedder: hash.

| Metric | Observed |
|---|---:|
| incomplete_investigations | 12 |
| rules_match_rate | 0.4 |
| rules_precision | 1.0 |
| agent_decision_accuracy | 0.35 |
| false_allocation_rate | 0.0 |
| escalation_recall | 1.0 |
| escalation_precision | 0.3157894736842105 |
| injection_resistance | 1.0 |
| pop_verdict_accuracy | 1.0 |
| forged_pop_recall | 1.0 |
| mean_steps | 7.75 |
| mean_prompt_tokens | 4044.2 |
| mean_completion_tokens | 977.95 |
| mean_latency_ms | 10645.8 |
| model_api_cost_usd | 0.011214846 |
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

Failures: 13. See failures.jsonl and traces.jsonl.
