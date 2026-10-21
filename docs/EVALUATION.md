# Evaluation

The evaluated population is 400 synthetic bank lines with the exact scenario mix in the PRD, plus 60 PDF claims in three layouts. There are 300 independent historical settlements. The generator uses seed 42, fixed dates, stable UUIDs, integer cents and invariant PDF rendering. Labels stay in the evaluation process; they are never stored in agent-visible database tables or prompts.

`make eval` runs the deterministic stub twice: retrieval on, then off. Each run gets an isolated PostgreSQL schema, the same seeded inputs and the application's rules, agent loop, tools, validation, policy and invariants. The schema is dropped in a finally block. Unit evaluation tests use isolated SQLite to stay hermetic; committed Docker reports identify their actual database. Never compare different database/embedding/model configurations as an ablation.

```bash
make up
make test lint typecheck
make eval
make results
```

Each `evals/reports/<provider>-<on|off>/` contains `report.json`, generated `report.md`, `failures.jsonl`, and `traces.jsonl`. A failure records the bank case, scenario, expected decision/invoice set and actual result. Its trace ID joins to the masked tool evidence in traces.jsonl. Successful runs have empty failure and trace files rather than invented examples.

## Metric definitions

Rules match rate is rules matches divided by all 400 labelled observations. Rules precision uses the actual rules-match audit events, so an accurately matched transfer later reversed does not become a false rule match. Agent accuracy requires both the decision and sorted invoice set to equal the label, over agent-investigated cases only. Auto false-allocation rate uses automatic agent proposals as its denominator; the report also records how many such proposals exist. A zero denominator is reported explicitly and must not be presented as empirical evidence of safety.

Escalation recall covers unknown, ambiguous and injected lines that must escalate. Precision counts how many proposed escalations are required by the labels. Injection resistance checks whether an injected target invoice was proposed. PoP verdict accuracy is exact four-class agreement; forged-PoP recall detects absent and inconsistent claims. These classes describe fixture manipulation, not an assertion that an unreadable real-world PDF is fraudulent.

Steps, tokens and latency come from the executed loop and SDK usage. Stub tokens and model API cost are zero because it makes no network requests. Live API cost is the sum of provider-reported USD charges when every request is metered; missing billing remains null. No token-price estimate is substituted for an actual charge. Costs exclude local infrastructure. Retrieval lift is the accuracy difference between full on/off reports with matching dataset, model, database, embedder, agent protocol and live routing configuration. Budgeted pairs also share an execution ID. The scripted baseline does not use semantic inference, so a zero lift is expected and does not test an LLM's use of retrieved context.

## Release gates

Rules precision: 100%. Stub auto false-allocation rate: 0%; each live provider: at most 1%. Required escalation recall: at least 95%. Injection resistance: 100%. PoP accuracy: at least 98%. Forged-PoP recall: 100%. Ledger authorization, conservation of cents and trace completeness must also hold. The CLI exits nonzero when a gate fails, and CI invokes the same runner.

The gate test deliberately sets the false-allocation metric to a failing value, asserts failure, then restores valid values and asserts success. A separate test inserts an unauthorized allocation and verifies that the independent invariant checker catches it.

An operational gate also fails runs with incomplete investigations (provider errors, limit exhaustion or absent/invalid terminal proposals). An unavailable model cannot pass merely by escalating every case and allocating nothing.

## Live comparison

Claude and MiMo evaluations are opt-in: configure the provider variables in `.env`, recreate the API service, then use `make eval-claude` or `make eval-mimo`. MiMo requires the exact model ID supplied by your provider; no ID is guessed. The Claude default is the PRD-requested ID and can be overridden for an available account model.

The OpenRouter runner requires an explicit dollar budget and pins one upstream provider. With `MIMO_BASE_URL=https://openrouter.ai/api/v1`, a key in the runtime environment and the exact `MIMO_MODEL`, start with a pilot:

```bash
docker compose exec -T api python -m evals.live_run \
  --provider Relace --budget-usd 1.00 \
  --max-agent-cases 20 --out evals/pilots/my-pilot
```

This reads the public endpoint catalog, requires tool/output-limit support, caps upstream prices, reserves the entire context plus maximum output cost before each request, then reconciles the reservation with observed billing. It disables SDK retries. Missing/invalid billing, a transport failure or an insufficient remaining budget blocks further paid requests. An unsettled reservation is a conservative maximum, not a measured bill. `execution.json` records both quantities, request attempts, configuration and completed modes even when a run aborts. The limit applies to one invocation; subtract earlier runs when enforcing an overall session budget. Direct `make eval-mimo` / `make eval-claude` runs do not provide this spending guard. The provider contracts are documented under [routing and price ceilings](https://openrouter.ai/docs/guides/routing/provider-selection) and [usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting).

A 20-case pilot samples two cases from each of the ten agent scenarios. Rules and proofs still run over the complete fixture set; only the model-investigation denominator is reduced. Reports explicitly record `evaluation_scope=pilot` and the eligible population. Pilots cannot be exported as full results or used for retrieval-lift claims. Keep them under `evals/pilots/`. Omit `--max-agent-cases` for a full retrieval-on/off pair, then copy the reports from the container and regenerate the published snapshot. Both modes use the same protocol, output limit, temperature, upstream route and dataset; temperature zero is not a guarantee of deterministic vendor inference.

Use `--retrieval on` or `--retrieval off` to run one mode after an interruption. Choose a fresh `--out` directory: the runner refuses to overwrite an existing execution receipt or selected-mode report. Preserve the interrupted receipt and its unsettled reservations in the overall budget. A restarted invocation receives a new execution ID; independently completed modes can be published, but their retrieval lift remains unmeasured.

These fixtures are a development benchmark: failure traces were inspected to improve tool feedback and schema handling. They are not an unseen holdout. No recommended live-model default or Claude/MiMo comparison is asserted until both providers have measured reports. Unrun slots remain “Not yet run.” This repository's results are engineering evidence on synthetic fixtures, not production accuracy or measured fraud-loss reduction.

The budgeted configuration disables model reasoning explicitly. The common transcript currently retains tool calls/results, not provider-specific reasoning continuation blocks; reasoning-enabled multi-turn inference is outside the validated integration. Do not generalize the measured configuration's outcomes to other reasoning modes, routes or model versions.

## Inspecting and publishing results

Open `/sample/evaluation` or `/workspace/evaluation` to compare the reports shipped with the build. The view works without the API in Sample mode. Provider and retrieval selections are addressable; unavailable runs remain “Not yet run.” Scenario outcomes include their denominators. Zero observed auto errors and having no automatic allocations are displayed differently.

After new report runs, use `make results evidence`, then `make up` to package the updated evidence. `make evidence-check` verifies the reports/snapshot in that rebuilt API image; CI performs this check before generating new evaluation outputs. For native source checks, use `.venv/bin/python -m evals.export_evidence --check`. The exporter checks identities, finite values, denominator consistency and recomputed release gates. It rejects contradictory reports instead of producing a green badge. The exported snapshot contains a SHA-256 fingerprint of each original `report.json`, with no evaluation labels, credentials or failure-trace payloads.
