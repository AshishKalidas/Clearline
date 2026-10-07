# Implementation decisions

- Use the existing project root for the section 19 layout; avoid a redundant nested clearline directory.
- Use SQLite only for isolated unit tests; Docker, demos and integration checks use PostgreSQL 16 and pgvector.
- Keep the configured embedding default local; explicitly select hash for offline demo/CI to avoid downloading a model.
- Demo credentials are public, local-only configuration; both services bind to loopback.
- Preserve excess EFT money as unapplied_cents in a resolved case; never overdraw an invoice even for an overpayment decision.
- Use a fictional beneficiary suffix of 0042; the sender's stored account suffix is not evidence of the business's beneficiary account.
- Keep historical bank observations separate from the 400 evaluation cases and authorize their synthetic ledger entries with rules-match audit events.
- Run evaluations in disposable PostgreSQL schemas; use SQLite only for hermetic unit evaluation tests.
- Do not estimate live model pricing; report SDK token usage and leave unknown API cost unpriced.
