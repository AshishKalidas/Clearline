# Architecture

Clearline separates investigation from authorization. The synthetic bank feed records observations; invoices record remaining obligations; allocations connect the two. PDFs record claims, never receipt of money.

## Runtime and flow

Docker Compose runs PostgreSQL 16 with pgvector/pg_trgm, a Python 3.12 FastAPI API and a compiled React workspace served by nginx. The browser uses `/api` through a same-origin proxy. Alembic executes as the migration owner before the API starts; health checks gate startup. The host defaults are web 5173, API 18000 and database 54329, bound to loopback.

CSV ingestion validates the complete file before writing, uses stable identities and hashes, and makes repeated bank imports idempotent. All monetary columns are BIGINT cents. Unique keys and check constraints enforce core table semantics. SQLAlchemy request transactions commit success and roll back exceptions.

Reconciliation holds a transaction-scoped PostgreSQL advisory lock shared with imports, proof verification and human decisions. Rules normalize invoice references and apply unique exact full-balance matches. A negative bank line reverses a uniquely attributable prior settlement within ten days, removes its allocations, restores invoice balances and preserves the historical audit trail. Injection-shaped text and linked proof mismatches veto exact allocations.

Each remaining line enters the bounded loop. The model receives an explicitly untrusted bank-text field, masked evidence and one provider-independent tool schema. Read arguments pass Pydantic validation; database reads run as `clearline_agent` with a bounded statement timeout. The loop records every attempted call/result, validates the terminal proposal, checks cited evidence and escalates on deadline, budget exhaustion, provider failure or repeated invalid submissions.

The deterministic policy independently authorizes eligible full matches. The application role then revalidates invoice balances and conservation, writes allocations, indexes the resolved case and records authorization in the same transaction. Partial/split/excess/duplicate and escalated cases remain pending for human review. A proposal is unique per bank line; already investigated lines are not rerun automatically.

## State and authorization

Bank statuses are `unmatched`, `in_review`, `matched`, `escalated` and `reversed`. Proposal statuses are `pending`, `auto_applied`, `approved` and `rejected`. A corrected resolution rejects the original recommendation and records the actual human resolution separately. A duplicate resolution records a case without applying funds; an overpayment settles only outstanding cents and preserves the surplus in `unapplied_cents`.

The ledger has three authorized sources: a rules match, a policy-approved proposal or a human decision. Independent evaluation invariants check authorization, auto limits, conflicting proof overrides, total allocated cents and tool-trace completeness. Deterministic rules are a separate authorization path; the model cannot bypass policy by requesting a rules allocation.

`clearline_owner` handles migration/seed/evaluation setup. `clearline_app` handles business writes but cannot update/delete audit events. `clearline_agent` can SELECT business tables and INSERT only proposals/audit events; it cannot mutate invoices, allocations or resolved cases. The loop's terminal proposal and audit records are persisted by application code, never arbitrary model SQL. PostgreSQL also protects audit events with an append-only trigger. The MCP process uses the agent identity inside an additional read-only transaction.

## Retrieval and provider boundaries

Resolved cases, customer notes and heading-chunked runbook sections have local 384-dimensional embeddings. pgvector cosine search uses IVFFlat indexes; candidate-customer filtering, exclusion of the current/reversed line and transactional indexing keep evidence relevant. Customer notes are embedded locally and exposed via customer lookup; similar-case and runbook search are explicit tools. With retrieval disabled these tools return empty lists.

HashEmbedder exercises the interfaces offline with deterministic token features. LocalEmbedder loads a pre-cached MiniLM model and never sends case text to an embedding service. A fresh corpus is required when changing vector semantics. Neither an approximate index nor a previous human resolution is authoritative evidence of this transfer's intent.

StubLLM is a scripted baseline. AnthropicLLM and OpenAICompatLLM translate common messages/tools into their SDK formats, bound retries/timeouts, parse tool replies and account for actual SDK token usage. Client lifecycles close transports even after failure. Live calls are opt-in; privacy masking is applied again at the outgoing adapter boundary.

## Evidence and PDFs

pdfplumber extracts required claim fields from three synthetic layouts. Pure verification compares positive, non-reversed bank lines with amount, ±2-day date tolerance, payer, reference, beneficiary suffix and optional claimed invoice. Verdicts and individual checks are stored; a mismatch blocks automatic allocations. Proof files receive server-generated UUID names, are size/page bounded and expire through the retention command. Uploading evidence never authorizes an allocation.

The review workspace displays the actual ordered tool results, case history, confidence, policy vetoes, proof checks and audit events. Human approval/correction rechecks live balances and records reviewer identity and notes. This identity is a local demonstration header, not production authentication.

## Routed workspaces

The interface has separate browser-only sample and API-backed workspace providers. The sample contains illustrative fixtures and temporary review simulation; it never calls the API or contributes to evaluation metrics. The connected provider polls health, actual metrics, bank observations, pending proposals and bounded masked `/activity` audit summaries. URL routes preserve proposal and tab selection; mode changes dispose outstanding reads. See [Design and interaction](DESIGN.md).

## CSV preparation and import boundary

`POST /ingest/{invoices|bank-lines}/preview` requires the workspace API key and validates up to 10 000 UTF-8 CSV records within the shared 5 MB upload limit. It opens no database session and calls no model. It returns the validated record count, known columns and first five records. The browser sends the original file again only after the user confirms import. Preview validates format, not current database identity conflicts.

Preview and import share the same schema/parser in `ingest/validation.py`. Duplicate/empty headers, malformed quoting, inconsistent column counts, invalid UTF-8 and invalid records fail before insertion. Diagnostics are bounded to 20 entries; unknown header names and rejected input values are excluded. Row numbers count logical records including the header. Imports revalidate independently, take the existing workflow lock, and commit all records plus an audit event together. Customer/invoice identity or invoice-date conflicts roll back the entire file; existing records are never overwritten. Audit summaries store inserted/skipped counts and a SHA-256 file fingerprint, without filenames or CSV content. Identical bank observations retain the existing canonical-content hash behavior.

## Published evaluation evidence

`evals/export_evidence.py` validates report identities, finite measurements, coherent counts, scenario totals, key ratios and recomputed release gates before exporting six provider/retrieval slots. Missing files remain null. The generated frontend JSON contains only validated report fields and fingerprints of the original source files. It is static published evidence, not operational workspace telemetry. `make evidence` regenerates it after evaluations; rebuilding packages that snapshot into nginx. CI checks the committed snapshot before fresh evaluation runs. The README table and the evidence page use the same report files.

## Response durability and verification boundaries

HTTP database dependencies use function scope: their transaction commits before FastAPI sends success. If commit fails, the request returns an error and both imported records and their audit event roll back. API handlers materialize response data while the session is open; no endpoint streams lazy ORM records after transaction completion. `test_transactions.py` injects a commit failure at this boundary.

Release gates accept only measured finite rates in [0, 1], reject boolean/coerced values, and require an explicitly observed zero incomplete-investigation count. The same gate function is used by the evaluation runner and published-evidence validator. MCP connectivity checks accept an empty result set and separately verify the exact read-only tool inventory. The protocol suite exercises both empty and populated databases, including an isolated PostgreSQL schema.
