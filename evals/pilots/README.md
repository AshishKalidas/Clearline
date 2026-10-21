# Live evaluation development record

These are development pilots, not full benchmark results. The model investigated only the explicitly reported agent-case count. The 400 bank cases and 60 proof documents describe the fixture population, not 400 live-model decisions per pilot. Full reports belong in `evals/reports/`.

| Attempt | What happened |
|---|---|
| `mimo-v2.6-flash-xiaomi-aborted` | A request did not settle within the investigation deadline. The runner stopped and retained its maximum request reservation; this is not an observed charge. |
| `mimo-v2.6-flash-relace` | Aborted on an application error before producing a complete report. |
| `mimo-v2.6-flash-relace-diagnostic` | Four cases per retrieval mode exposed investigations that exhausted their tool-call budget. Both operational gates failed. |
| `mimo-v2.6-flash-relace-retry` | Reproduced the application error: PostgreSQL `SUM(bigint)` returned `Decimal`, which could not be serialized into the audit JSON. |
| `mimo-v2.6-flash-relace-refined` | Twenty cases per mode after fixing aggregate serialization and adding citation/budget/schema feedback. Accuracy was 7/20 with retrieval and 9/20 without; 12 and 13 investigations respectively were incomplete. Neither mode made automatic allocations. Both operational gates failed. |

The final protocol additionally asks for one tool per turn and enforces the reserved terminal-call slots inside batched responses. Pilots from earlier protocol versions remain here to document failures; they are not combined with the full run or used to claim retrieval lift. Fixes changed application/tool handling, not fixture labels or release thresholds. The dataset has been inspected during development and is not an unseen holdout.

Each execution receipt records measured provider billing separately from conservative unsettled reservations. Early application-error attempts have an empty `completed_modes` object; their original receipts predate the separate execution-error field. A small route probe receipt records one metered request without retaining its prompt or response. Credentials are absent from these artifacts.
