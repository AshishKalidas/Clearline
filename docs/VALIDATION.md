# Executed validation

Build verification on 7 October 2026. All financial fixtures are synthetic. The checks below were executed locally; the GitHub Actions workflow is configured to repeat them, but no remote GitHub workflow or deployment is claimed.

| Check | Observed result |
|---|---|
| Docker backend suite | 58 passed; 95.16% statement coverage on `backend/app`; required threshold 85% |
| Ruff lint and formatting | Clean |
| Strict mypy | Clean on `backend/app` and `mcp_server` (55 source files) |
| Frontend unit suite | 8 tests passed in 3 files |
| Frontend build | TypeScript check and Vite production build passed; React bundle 173.47 kB before gzip |
| Browser against nginx + actual API | Approve, reject, correct, invoice choices, genuine/absent PDF upload and laptop-width overflow checks passed (2 Playwright tests) |
| Live SDK adapters | Recorded HTTP response tests exercised both real SDKs, retries, request masking, tool translation, malformed replies, usage and transport closure; no paid network calls |
| MCP stdio client | Initialized; exactly 8 read-only tools listed; `search_invoices` succeeded against PostgreSQL |
| MCP safety | Every tool called through the protocol; returned PII-shaped fixture strings and echoed invalid arguments masked; unknown write tool and fractional cents rejected; database transaction rejected an audit INSERT otherwise permitted to the agent role |
| PostgreSQL evaluation | Retrieval on/off: every release gate passed; 400 bank cases, 228 agent cases, 54 agent auto allocations, 0 wrong auto allocations and 60 proof documents per run |
| README generation | Generated table verified equal to the committed report-derived table |
| Clean-checkout demo | Exported tracked/staged source only, no `.env`, virtual environment, `node_modules` or local Docker settings; fresh isolated Compose project/volumes built, migrated, seeded and reconciled successfully |
| Idempotent demo | Repeated seed/run preserves existing history and resolutions; no additional agent investigations on already processed lines |
| Synthetic PDFs | All three generated layouts rendered and visually inspected; reproducibility and 60-file verdict tests passed |

The clean demo used alternate loopback ports (web 5175, API 18001, PostgreSQL 54330) to preserve the active workspace. Browser workflows were repeated against those freshly seeded services. The main demo remains available on its default web port 5173 and API port 18000.

The current report files are the source of truth for exact evaluation metrics and timing. Stub throughput is machine/load dependent; synthetic decision accuracy is not an estimate of live-model quality. The local embedding interface is tested with a stand-in cached encoder; a downloaded MiniLM checkpoint and real provider inference were not benchmarked. Missing live results remain “not yet run.”

A credential/private-key pattern scan of committed source trees found no matches. This is a targeted repository check, not a general security audit. Public local Docker passwords and the local demo mutation key are intentionally documented demonstration values.
