# Executed validation

Build verification updated on 21 October 2026; the base platform was completed on 7 October 2026. All financial fixtures are synthetic. The checks below record local execution. The GitHub Actions workflow repeats the release checks on pushes and pull requests; its current status is linked from the README. The public static demo is described in [Deployment](DEPLOYMENT.md); the API-backed application remains a local Docker workspace.

| Check | Observed result |
|---|---|
| Docker backend suite | 136 passed; 95.48% statement coverage on `backend/app`; required threshold 85% |
| Ruff lint and formatting | Clean |
| Strict mypy | Clean on `backend/app`, `mcp_server` and all evaluation modules (66 source files) |
| Frontend unit suite | 37 tests passed in 8 files |
| Frontend build | TypeScript check and Vite production build passed; application bundle 276.23 kB before gzip with both published live reports; standalone demo build also passed |
| Standalone public demo | 2 Playwright workflows passed locally and against the anonymous Vercel production URL; deep links, review/activity, proof scenarios, reports and phone navigation worked without API requests |
| Browser against nginx + actual API | 11 Playwright tests passed: actual reviews/uploads, API-blocked sample use, deep links/history, mobile layouts, saved appearance, reduced transparency/motion, increased contrast, live polling pause/recovery, navigation during a pending approval, scrolling navigation blur, offline published evidence, and actual CSV validation/import/deduplication in desktop/phone layouts |
| Live SDK adapters | Recorded HTTP response tests exercised both real SDKs, retries, request masking, tool translation, malformed replies, usage and transport closure; the unit suite makes no paid network calls |
| MCP stdio client | Initialized; exactly 8 read-only tools listed; `search_invoices` succeeded against PostgreSQL |
| MCP safety | Every tool called through the protocol; returned PII-shaped fixture strings and echoed invalid arguments masked; unknown write tool and fractional cents rejected; database transaction rejected an audit INSERT otherwise permitted to the agent role |
| PostgreSQL scripted baseline | Retrieval on/off: every release gate passed; 400 bank cases, 228 agent cases, 54 agent auto allocations, 0 wrong auto allocations and 60 proof documents per run |
| Live MiMo retrieval on | 400 bank cases, 228 agent investigations, 50.88% decision accuracy, 10 automatic agent allocations, zero wrong automatic allocations and zero invariant errors; 112 incomplete investigations failed the operational gate |
| Live MiMo retrieval off | Independently restarted full run: 400 bank cases, 228 agent investigations, 55.70% decision accuracy, 7 automatic agent allocations, zero wrong automatic allocations and zero invariant errors; 99 incomplete investigations failed the operational gate; no paired retrieval lift claimed |
| README generation | Generated table verified equal to the committed report-derived table |
| Clean-checkout demo | Exported tracked/staged source only, no `.env`, virtual environment, `node_modules` or local Docker settings; fresh isolated Compose project/volumes built, migrated, seeded and reconciled successfully |
| Idempotent demo | Repeated seed/run preserves existing history and resolutions; no additional agent investigations on already processed lines |
| Synthetic PDFs | All three generated layouts rendered and visually inspected; reproducibility and 60-file verdict tests passed |

The clean demo used alternate loopback ports (web 5175, API 18001, PostgreSQL 54330) to preserve the active workspace. Browser workflows were repeated against those freshly seeded services. The main demo remains available on its default web port 5173 and API port 18000. The new workspace routing and all eleven browser workflows were verified against the production nginx build on those default ports.

The current report files are the source of truth for exact evaluation metrics and timing. Stub throughput is machine/load dependent; synthetic decision accuracy is not an estimate of live-model quality. The local embedding interface is tested with a stand-in cached encoder; a downloaded MiniLM checkpoint was not benchmarked. Live inference uses nonsemantic hash retrieval. Missing published runs remain “Not yet run.”

Gitleaks 8.30.1 scanned complete Git history with redacted output and found no leaks. The release archive was checked against its published SHA-256 checksum. Repository-local ignore rules were verified with global Git exclusions disabled: `.env` and nested environment variants are ignored while `.env.example` remains eligible for tracking. Public local Docker passwords and the local demo mutation key are intentionally documented demonstration values. Pattern scanning is not a general security audit.

## Workspace redesign checks

Screenshots for the sample overview, connected overview, dark appearance and phone layout were captured from the completed interface and visually inspected. A production browser run exposed a queue-load navigation race; implicit selection now updates local state instead of issuing a redirect. A delayed-approval regression also proves that completing an action does not pull a reviewer away from another page. Native radio controls handle appearance/proof choices. The saved theme is applied before React mounts, preventing a light first frame in dark mode. Browser traces and reports are excluded from Docker build contexts and Git.

## Navigation and maintainability follow-up

The production stylesheet originally retained only the WebKit-prefixed backdrop filter, which Chromium ignored. Ordering the standard declaration last preserves both forms in the built asset. A separate gradient scrim softens the top viewport gap. Scrolled desktop/phone screenshots in both appearances were visually inspected; the production browser regression verifies active blur, clickable navigation and opaque increased-contrast fallback. Existing reduced-transparency, focus, routing and financial workflows pass with the fix.

The focused frontend review removed dead markup/imports and redundant filter handling, moved the shared request contract out of the sample implementation, enabled unused-local/parameter and switch-fallthrough compiler errors, and corrected notification lifetimes and stale invoice responses. Unit regressions exercise a parent update during a notification and an invoice response arriving after correction is cancelled/reopened. All frontend checks and the full Docker backend suite were rerun.

## Import and evidence refinement

The October 21 pass adds guided CSV imports and an offline-capable report explorer. The Docker suite now includes malformed/ambiguous UTF-8 CSV, full-file preview validation beyond the first five records, bounded safe errors, authenticated preview, unchanged database/audit counts after preview, idempotent import, and whole-file rollback on an existing-invoice conflict. Report tests reject non-finite measurements, inconsistent ratios/counts/flags, missing operational measurements and directory-identity mismatches. A coherent failed report remains publishable with its failed gate visible; absent live runs remain null.

Both PostgreSQL stub evaluations were rerun on October 21: retrieval on/off passed every gate, with 400 bank cases, 228 agent investigations, 54 automatic agent allocations, zero wrong auto allocations and 60 proofs per run. The README table and generated frontend snapshot match those current report files. The production browser suite exercises invalid-file feedback, explicit import confirmation, both CSV kinds, repeated import skips, activity events, template download, report query/history state, API-blocked evidence access, and desktop/phone overflow checks. Light/dark screenshots were visually inspected. A template ID collision with seeded history was caught during browser validation and corrected before release.

The clean-checkout smoke check recorded above predates this refinement. The original import/evidence pass rebuilt and tested the main Docker/nginx application with its existing synthetic ledger. Public deployment and remote CI verification were performed in subsequent passes, as recorded below. No paid live-model run had been performed at that stage.

## Transaction and verification contracts

Commit-failure injection confirms that HTTP success follows database commit: a refused commit returns 500 and leaves no imported bank records or import audit event. The shared database dependency enforces the same boundary for review writes. Rate-gate regressions cover missing metrics, booleans, strings, non-finite and out-of-range values, operational completion evidence and inclusive provider thresholds. MCP stdio tests accept empty ledgers on SQLite and an isolated PostgreSQL schema while retaining the existing populated-tool and read-only checks. CI executes protocol checks before and after seeding, pins action implementations and preserves failure diagnostics.

## Import lifecycle contracts

The import controller now represents idle, validating, ready, importing and complete states as a discriminated TypeScript union. Ready/active/completed states require their file and preview data; only a confirmed ready state can write. Seven controller tests cover file/confirmation identity, synchronous duplicate-event suppression, cancellation on unmount, expired responses, completion after navigation, safe error/retry state and disabled-workspace isolation. A browser regression delays a genuine import response, navigates away, releases the response and verifies that the write completes and the selected route remains unchanged.

[GitHub release verification](https://github.com/AshishKalidas/Clearline/actions/runs/39589588539) completed successfully on a clean Ubuntu runner for the transaction/verification changes, including both MCP data states, retrieval-on/off evaluation, backend/web checks and the browser workflows. The workflow repeats the same release process for subsequent commits.

## Configuration and proof-verification contracts

Configuration regressions verify that provider/mutation keys and database URLs do not appear in settings diagnostics, live SDK constructors receive the unwrapped test key without making a request, an empty mutation key fails configuration, and invalid/non-ASCII headers return 401. CI independently scans complete Git history with a pinned, checksum-verified Gitleaks binary. Neither Docker build context admits local environment files.

Temporary synthetic environment probes at the repository root, frontend root and nested frontend source directory were excluded from the rebuilt API image and frontend build stage. All probes and the temporary builder tag were removed after verification.

Proof verification now has explicit idle, verifying, loading-bank and complete states. UI regressions cover locked inputs, synchronous duplicate-event suppression, invoice-change invalidation, exact bank-record lookup, preservation of a saved verdict when its supplementary read fails, upload completion after navigation, read cancellation and failed-upload retry. A backend regression places the linked bank record outside a 1,000-record feed and confirms that it remains individually addressable. The browser workflow checks the actual linked bank observation before proceeding to the next upload.

## Public demo deployment

The standalone demo was built and deployed to [clearline-ecru.vercel.app](https://clearline-ecru.vercel.app) in the owner's Vercel project. Anonymous HTTP checks confirmed the SPA routes, JavaScript/CSS content types and security headers. The same two Playwright workflows passed locally and at the production URL; they block/count API requests and exercise reviews, activity, proof scenarios, evidence reports, deep-link refreshes, connected/legacy redirects and phone layouts. Desktop and phone screenshots of the actual production URL were visually inspected. The complete Docker/nginx application's eleven browser workflows also passed after adding the demo build.

The CLI dry run contained 62 frontend files and excluded environment files, Vercel credentials, dependencies, browser artifacts and backend data. The repository's GitHub website field and README link to the public alias. Deployment settings and the distinction between simulated browser actions and the full API-backed application are documented in [Deployment](DEPLOYMENT.md).
