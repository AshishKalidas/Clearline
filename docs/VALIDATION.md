# Executed validation

Build verification updated on 21 October 2026; the base platform was completed on 7 October 2026. All financial fixtures are synthetic. The checks below were executed locally; the GitHub Actions workflow is configured to repeat them, but no remote GitHub workflow or deployment is claimed.

| Check | Observed result |
|---|---|
| Docker backend suite | 80 passed; 95.48% statement coverage on `backend/app`; required threshold 85% |
| Ruff lint and formatting | Clean |
| Strict mypy | Clean on `backend/app`, `mcp_server` and the report exporter (58 source files) |
| Frontend unit suite | 20 tests passed in 7 files |
| Frontend build | TypeScript check and Vite production build passed; React bundle 268.84 kB before gzip |
| Browser against nginx + actual API | 10 Playwright tests passed: actual reviews/uploads, API-blocked sample use, deep links/history, mobile layouts, saved appearance, reduced transparency/motion, increased contrast, live polling pause/recovery, navigation during a pending approval, scrolling navigation blur, offline published evidence, and actual CSV validation/import/deduplication in desktop/phone layouts |
| Live SDK adapters | Recorded HTTP response tests exercised both real SDKs, retries, request masking, tool translation, malformed replies, usage and transport closure; no paid network calls |
| MCP stdio client | Initialized; exactly 8 read-only tools listed; `search_invoices` succeeded against PostgreSQL |
| MCP safety | Every tool called through the protocol; returned PII-shaped fixture strings and echoed invalid arguments masked; unknown write tool and fractional cents rejected; database transaction rejected an audit INSERT otherwise permitted to the agent role |
| PostgreSQL evaluation | Retrieval on/off: every release gate passed; 400 bank cases, 228 agent cases, 54 agent auto allocations, 0 wrong auto allocations and 60 proof documents per run |
| README generation | Generated table verified equal to the committed report-derived table |
| Clean-checkout demo | Exported tracked/staged source only, no `.env`, virtual environment, `node_modules` or local Docker settings; fresh isolated Compose project/volumes built, migrated, seeded and reconciled successfully |
| Idempotent demo | Repeated seed/run preserves existing history and resolutions; no additional agent investigations on already processed lines |
| Synthetic PDFs | All three generated layouts rendered and visually inspected; reproducibility and 60-file verdict tests passed |

The clean demo used alternate loopback ports (web 5175, API 18001, PostgreSQL 54330) to preserve the active workspace. Browser workflows were repeated against those freshly seeded services. The main demo remains available on its default web port 5173 and API port 18000. The new workspace routing and all ten browser workflows were verified against the production nginx build on those default ports.

The current report files are the source of truth for exact evaluation metrics and timing. Stub throughput is machine/load dependent; synthetic decision accuracy is not an estimate of live-model quality. The local embedding interface is tested with a stand-in cached encoder; a downloaded MiniLM checkpoint and real provider inference were not benchmarked. Missing live results remain “not yet run.”

A credential/private-key pattern scan of committed source trees found no matches. This is a targeted repository check, not a general security audit. Public local Docker passwords and the local demo mutation key are intentionally documented demonstration values.

## Workspace redesign checks

Screenshots for the sample overview, connected overview, dark appearance and phone layout were captured from the completed interface and visually inspected. A production browser run exposed a queue-load navigation race; implicit selection now updates local state instead of issuing a redirect. A delayed-approval regression also proves that completing an action does not pull a reviewer away from another page. Native radio controls handle appearance/proof choices. The saved theme is applied before React mounts, preventing a light first frame in dark mode. Browser traces and reports are excluded from Docker build contexts and Git.

## Navigation and maintainability follow-up

The production stylesheet originally retained only the WebKit-prefixed backdrop filter, which Chromium ignored. Ordering the standard declaration last preserves both forms in the built asset. A separate gradient scrim softens the top viewport gap. Scrolled desktop/phone screenshots in both appearances were visually inspected; the production browser regression verifies active blur, clickable navigation and opaque increased-contrast fallback. Existing reduced-transparency, focus, routing and financial workflows pass with the fix.

The focused frontend review removed dead markup/imports and redundant filter handling, moved the shared request contract out of the sample implementation, enabled unused-local/parameter and switch-fallthrough compiler errors, and corrected notification lifetimes and stale invoice responses. Unit regressions exercise a parent update during a notification and an invoice response arriving after correction is cancelled/reopened. All frontend checks and the full Docker backend suite were rerun.

## Import and evidence refinement

The October 21 pass adds guided CSV imports and an offline-capable report explorer. The Docker suite now includes malformed/ambiguous UTF-8 CSV, full-file preview validation beyond the first five records, bounded safe errors, authenticated preview, unchanged database/audit counts after preview, idempotent import, and whole-file rollback on an existing-invoice conflict. Report tests reject non-finite measurements, inconsistent ratios/counts/flags, missing operational measurements and directory-identity mismatches. A coherent failed report remains publishable with its failed gate visible; absent live runs remain null.

Both PostgreSQL stub evaluations were rerun on October 21: retrieval on/off passed every gate, with 400 bank cases, 228 agent investigations, 54 automatic agent allocations, zero wrong auto allocations and 60 proofs per run. The README table and generated frontend snapshot match those current report files. The production browser suite exercises invalid-file feedback, explicit import confirmation, both CSV kinds, repeated import skips, activity events, template download, report query/history state, API-blocked evidence access, and desktop/phone overflow checks. Light/dark screenshots were visually inspected. A template ID collision with seeded history was caught during browser validation and corrected before release.

The clean-checkout smoke check recorded above predates this refinement. The current pass rebuilt and tested the main Docker/nginx application with its existing synthetic ledger; no public deployment, remote CI execution or paid live-model run was performed.
