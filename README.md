# Clearline

**Every payment. A clear decision.**

[![Release gates](https://github.com/AshishKalidas/Clearline/actions/workflows/ci.yml/badge.svg)](https://github.com/AshishKalidas/Clearline/actions/workflows/ci.yml)

[**Open the interactive demo →**](https://clearline-ecru.vercel.app)

An evidence-first EFT reconciliation platform: exact rules handle predictable payments, a bounded agent investigates exceptions, and deterministic policy controls what reaches the ledger.

> I built Clearline to help finance teams resolve unmatched transfers and verify payment claims, so they can close their books and release goods with confidence, because poor references, complex payments and convincing PDFs make manual reconciliation slow and error-prone.

The public demo needs no account. Explore eight sample exceptions, approve or correct a proposal, inspect its evidence and audit trail, try three payment-proof scenarios, and compare the published evaluation reports. Sample decisions stay in your browser and reset on refresh. It uses fictional fixtures and simulated actions; actual CSV/PDF processing, model investigations and durable ledger writes run in the complete Docker workspace below. [Deployment details](docs/DEPLOYMENT.md).

![Clearline workspace overview](docs/images/workspace-overview.png)

## The problem → the solution

Businesses accepting EFTs receive mistyped references, missing references, partial payments, duplicate transfers and one payment covering multiple invoices. A clerk must reconstruct the payer's intent. A forged proof-of-payment PDF adds a second risk: goods leave before money arrives.

Clearline gives that investigation a controlled workflow:

1. **Rules settle the obvious cases.** Exact references and full balances match deterministically; attributable reversals unwind prior allocations.
2. **The agent gathers evidence.** Validated read-only tools inspect invoices, customers, payment history, local case retrieval and the runbook. Its only terminal action is a structured proposal.
3. **Policy or a person authorizes the resolution.** Automatic full matches must satisfy every safety condition. Reviewers approve, reject or correct the rest with an ordered evidence trace.
4. **Payment proofs are checked independently.** Amount, date, payer, reference and beneficiary must agree with the bank feed. An uploaded PDF never creates an allocation.

**A proof of payment is a claim; the bank feed is the evidence.**

## Run the complete demo

Prerequisites: Docker with Compose, a running Docker engine, and `make`. No Python, Node, model credential or manual database setup is required on the host.

```bash
make demo
```

The command builds the services, waits for health checks, applies migrations, loads 400 synthetic bank cases and 300 historical settlements, generates 60 proof PDFs, reconciles the feed and opens **http://localhost:5173**. The app starts in the browser-only **Sample** workspace; choose **Connected** for the seeded API-backed ledger. First-time image and dependency downloads require internet; the seeded application, stub evaluation and tests make no model requests and work offline once images are built.

API documentation: **http://localhost:18000/docs**. The public local demo key is `clearline-local-demo`; the UI supplies it by default. Change reviewer identity, appearance and the connected key in **Settings**. Services bind to loopback. Docker volumes retain decisions between restarts; repeated seeding/reconciliation is idempotent.

Try the workflow:

- **Sample** works without the API: explore eight illustrative exceptions, temporary review actions and three simulated proof outcomes. It sends no financial action to the backend. Reset from Overview or Settings; page refresh also resets the sample.
- **Connected** uses the actual API. Its live panel shows health, configured agent, recent audited decisions and last sync, with ten-second polling, pause/resume and manual refresh. All supplied bank data is still synthetic.
- Each view has a shareable URL: `/sample/overview`, `/workspace/review`, `/workspace/proofs`, `/workspace/activity` and `/workspace/settings`. Selected proposal, tab and review filters survive deep-link refresh and browser history.
- Select a split or partial payment, read **Evidence** and **Audit trail**, then approve (`A`), reject with a note (`R`), or correct the invoice allocations in integer cents.
- In **Connected**, open **Payment proofs** and upload `evals/datasets/seed-42/pops/proof-001.pdf` for a verified claim, `proof-031.pdf` for an absent payment, or `proof-046.pdf` for an amount mismatch. Leave the optional claimed invoice blank for this walkthrough.
- Open **Bring in your records** from Overview or **Data imports** in Settings. Download the paired fictional CSV templates, import invoices first, then bank observations. Validation previews the first five records after checking the whole file; saving requires an explicit import. Repeated identical imports are skipped.
- Open **Inspect the evidence** from Overview to compare published retrieval-on/off reports, inspect denominators and release gates, and download a report snapshot. It works in Sample with the API offline. Each published run includes its execution settings and source provenance.
- In **Connected**, reconcile again: already reviewed lines are not allocated a second time.

For headless environments use `CLEARLINE_NO_BROWSER=1 make demo`. To avoid port conflicts, export `CLEARLINE_WEB_PORT`, `CLEARLINE_API_PORT` and/or `CLEARLINE_DB_PORT` before starting Compose. `make down` stops the services and preserves data.

## Architecture

```mermaid
flowchart LR
    CSV[CSV / mock bank feed] --> Ingest[Validated idempotent ingest]
    Ingest --> Rules[Exact rules + reversals]
    Rules -->|exceptions| Agent[Bounded investigation agent]
    Retrieval[Local case + runbook retrieval] --> Agent
    Agent --> Proposal[Validated structured proposal]
    Proposal --> Policy[Deterministic policy]
    Policy -->|safe full match| Ledger[Integer-cent allocations]
    Policy -->|review required| Human[React review + correction]
    Human --> Ledger
    Human --> Retrieval
    PDF[Payment proof PDF] --> Verify[Bank-feed verification]
    Verify --> Policy
    Agent --> Audit[Masked append-only audit]
    Human --> Audit
    MCP[Read-only stdio MCP] --> Retrieval
```

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic · PostgreSQL 16 / pgvector / pg_trgm · React 18 · TypeScript · Vite · plain CSS · nginx · typed model adapters · MCP SDK.

The model-facing database role cannot insert allocations or update invoices. The agent is bounded to eight tool calls and 60 seconds per investigation. Invalid arguments consume the budget; repeated invalid proposals, unavailable providers and exhausted limits escalate. Evidence citations must refer to successful tool calls. Financial mutations share a transaction lock, revalidate current balances and commit allocations, case indexing and audit evidence together. The API acknowledges success only after that commit; a commit-time failure returns an error and rolls back the write.

## Verification

The reproducible evaluation suite exercises 400 synthetic bank cases, 228 agent investigations, 300 historical settlements and 60 payment-proof documents across three layouts. Independent checks cover allocation authorization, conservation of integer cents, evidence traceability and human-review boundaries.

Strict Python and TypeScript checks, backend integration tests and browser workflows run in CI. Reports retain scenario-level outcomes, execution settings and source fingerprints for inspection in the app's report explorer.

[Evaluation methodology](docs/EVALUATION.md) · [Detailed results](EVALUATION_RESULTS.md) · [Validation notes](docs/VALIDATION.md)

## What a human signs off

Automatic agent allocations require a **single full invoice match**, confidence ≥ 0.90, amount ≤ R 5 000,00, no risk flags, no linked proof mismatch and at least one prior case for the customer. Exact rules also withhold allocations when proof evidence conflicts.

Partial, split, excess, duplicate, ambiguous, risky and unfamiliar-customer cases require review. Rejection and correction require a note; approving conflicting proof evidence requires an explained override. Excess remains unapplied, duplicates create no allocation, and review writes are validated against current balances. See [Human sign-off](docs/HUMAN_SIGNOFF.md).

## Engineering you can inspect

| Concern | Implementation and evidence |
|---|---|
| Agent boundaries | [Bounded loop](backend/app/agent/loop.py), one shared tool schema, recorded-response tests for both live SDKs |
| Ledger safety | [Pure rules](backend/app/matching/rules.py), [policy](backend/app/agent/policy.py), database constraints, review revalidation and independent invariant checks |
| Retrieval | Local 384-dimensional embeddings, customer-filtered pgvector cosine search, transactionally indexed resolutions, on/off ablation |
| Privacy | Stable per-investigation masking, outbound-request capture, masked audit/retrieval text, least-privilege roles and proof-file retention |
| Product workflow | Routed overview, isolated sample mode, live activity, validated CSV previews/imports, human corrections, keyboard actions and proof checks; browser tests exercise the real API |
| Evaluation transparency | Offline-capable report explorer, explicit unmeasured live runs, scenario denominators, recomputed release gates and SHA-256 provenance |
| Maintainability | Strict Python/TypeScript checks, unused-code gates, a [typed import lifecycle](web/src/imports/useCsvImport.ts), small request adapters and regressions for async UI races |
| Reproducibility | Deterministic data/PDF generator, locked dependencies, Docker migrations, disposable evaluation schemas and generated results |
| Integrations | Eight masked read-only tools over stdio using the [official MCP SDK](docs/MCP.md) |

## A considered interface

The interface follows the supplied Apple design reference: floating Liquid Glass navigation, opaque financial surfaces, system typography, restrained blue actions and responsive layouts. Light, dark and system appearances are available, with reduced-motion, reduced-transparency and increased-contrast fallbacks. [Design and interaction details](docs/DESIGN.md) explain routing, sample isolation and polling.

![Connected workspace with actual API activity](docs/images/workspace-connected.png)

## Verify and develop

```bash
make up
make lint typecheck test     # strict types, formatting, ≥85% backend coverage
make eval                   # stub: retrieval on + off; safety gates must pass
make results                # regenerate the detailed results document
make evidence               # package validated reports for the evidence page
make up                     # rebuild the app with those report snapshots
make evidence-check         # verify the packaged snapshot against its source reports
make mcp-check              # real client initialization, tool listing and search
make purge                  # delete expired uploaded proof files
```

GitHub Actions runs the backend checks, synthetic release gates, web build/unit tests and actual browser review/proof/import workflows. It also verifies that the committed evidence snapshot matches its source reports before running new evaluations. Evaluation gates are enforced by the runner. [Validation notes](docs/VALIDATION.md) describe what was executed locally.

For frontend development (Node 24):

```bash
cd web
npm ci
npm run dev                 # Vite uses the local API on port 18000
npm test
npm run build
npm run build:demo           # standalone sample deployment; no API required
npx playwright install chromium
npm run test:e2e             # Docker services and seeded stub data must be running
npm run test:demo            # builds/serves the public demo and checks it in Chromium
```

For Python development: create a Python 3.12 virtual environment and `pip install -e '.[dev]'`. Docker pins the tested dependency versions in `requirements.lock`; the frontend uses `package-lock.json`. Run SQLite unit tests without Docker using `EMBEDDER=hash pytest`; PostgreSQL-only integration tests run in `make test`.

## Model and retrieval configuration

The investigation loop uses interchangeable model adapters with a shared tool contract. The default Docker workspace runs offline with a deterministic adapter, making the full review workflow reproducible without credentials. Configure a live provider through `.env.example` and follow the [model setup and budgeted evaluation guide](docs/EVALUATION.md#live-comparison). Provider configuration stays on the server; public-demo visitors do not trigger paid requests.

`.env.example` is a committed setup template containing public demo values and empty provider keys. Keep real credentials in `.env` or the runtime environment. Git and both Docker build contexts exclude `.env` and its variants, such as `.env.local` and `.env.production`. CI scans complete Git history for credentials with a checksum-pinned Gitleaks release.

The Docker demo uses deterministic local hash embeddings. An optional local sentence-transformer adapter supports semantic retrieval with pre-cached weights. See [retrieval configuration](docs/ARCHITECTURE.md) for indexing and embedding details.

## Documentation and deployment scope

The hosted demo uses fictional data and browser-local sample actions. The Docker workspace provides API-backed imports, proof processing, investigations and persistent review decisions. Customer deployment requires identity and tenant controls, bank-feed integration and validation against representative customer records. See [deployment details](docs/DEPLOYMENT.md), [privacy](docs/PRIVACY.md) and [the customer validation path](docs/EVALUATION.md#validation-with-representative-customer-data).

[Design and routing](docs/DESIGN.md) · [Architecture](docs/ARCHITECTURE.md) · [Human sign-off](docs/HUMAN_SIGNOFF.md) · [Evaluation](docs/EVALUATION.md) · [MCP](docs/MCP.md) · [Reconciliation runbook](docs/runbook.md) · [Decisions](docs/DECISIONS.md) · [PRD](Clearline_PRD.md)
