# Privacy and safety boundaries

Every supplied customer, invoice, transfer, account suffix and PDF is synthetic. No real bank or personal dataset is connected. This is a POPIA-minded engineering design, not a claim of regulatory compliance.

## Masking

`Masker` replaces email addresses, 13-digit identifiers, South African phone-shaped strings and 8–11-digit account-shaped strings with stable tokens such as `[EMAIL_1]` and `[ACCOUNT_1]`. The mapping exists only in memory for one investigation. Invoice identifiers, UUIDs and numeric integer-cent values remain available for validation. Structured JSON is walked before masking so financial numbers are not accidentally treated as text account numbers. The local mapping may restore a validated read query; it is never sent to a provider.

The loop masks initial context, tool arguments/results and audit payloads. Both SDK adapters mask outgoing messages again; recorded HTTP transport tests inspect the actual serialized SDK request. Retrieval summary text and customer notes are masked before embedding, and MCP results and SDK validation-error messages are masked before protocol output. Actor strings and unexpected dictionary keys are redacted as well.

Pattern redaction does not remove arbitrary names, addresses or every possible international identifier. Fictional customer names, invoice IDs, amounts, dates and relationships can still be present in model context. Raw imported references/customer notes remain in the local business database for investigation; the review API exposes local evidence. Synthetic-only use remains the boundary for this demo.

## Data leaving the machine

Default stub/hash operation sends no business context to third-party model or embedding services. Initial dependency/image installation requires network access. LocalEmbedder loads a pre-cached MiniLM model; it does not silently download or call an embedding endpoint.

Opting into Claude or an OpenAI-compatible MiMo endpoint sends masked bank/invoice/customer/runbook/case context and tool schemas to the configured vendor. Credentials come from environment variables and are never part of prompts or reports. SDK errors become safe escalation reasons rather than echoed response bodies. Real model usage is measured from SDK token counts; live cost is left unpriced.

MCP itself is local stdio, but the connecting host may send its returned masked financial facts to that host's model provider. Evaluate the host's data handling before connecting any real dataset. Tool annotations are descriptive; actual database privileges and read-only transactions enforce the boundary.

## Roles and audit

The migration owner performs schema setup and synthetic seeding. The API role mutates business records; the agent role has SELECT on business tables and INSERT only on proposals/audit, with no invoice or allocation write privilege. MCP requires `clearline_agent` on PostgreSQL and opens read-only transactions, preventing even its otherwise permitted proposal inserts. Audit events deny update/delete to runtime roles and have an append-only PostgreSQL trigger.

Local credentials in Compose and `.env.example` are public demo values, not deployed secrets. Docker binds to loopback. Git and both Docker build contexts exclude `.env` and `.env.*`, except the setup template `.env.example`; runtime storage, virtual environments and browser artifacts are also excluded. CI scans full Git history with a checksum-pinned Gitleaks binary and redacts findings. Pattern scanning cannot establish that every possible secret is absent.

Pydantic secret fields mask provider and mutation keys in settings representations and JSON serialization. Database URLs are excluded from those diagnostics; their passwords remain available to the connection layer. Only the authentication boundary, demo client and provider SDK constructors unwrap keys. An empty mutation key is rejected during configuration, and malformed/non-ASCII request keys receive 401. The browser stores its local mutation key and reviewer in sessionStorage. Production auth/tenant isolation are explicit non-goals.

## Retention

Uploaded PDFs use UUID filenames, never client-provided paths. `make purge` removes only regular PDF files older than `POP_RETENTION_DAYS` (default 30); it skips symlinks and unrelated files. This is an explicit command, not an automatically scheduled job. It does not erase extracted fields, verification metadata, resolutions, audits, database backups or committed synthetic fixtures. A failed transaction can leave an unreferenced upload file; retention eventually removes it. Production retention would need a broader, scheduled lifecycle and business policy.
