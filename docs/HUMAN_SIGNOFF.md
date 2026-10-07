# Human sign-off

Clearline is a fictional single-workspace finance tool. Reviewer identities come from `X-Reviewer`; mutation authorization uses `X-API-Key`. Neither substitutes for authenticated production users or separation of duties.

## Automatic paths

Exact rules apply a unique open invoice only when its normalized number and outstanding cents equal a positive bank transfer. Suspicious instruction-shaped references and linked mismatched proof evidence withhold the match. Reversals require a unique settled transfer with equal absolute amount, normalized payer/reference and a date window of ten days.

Agent auto application requires every condition:

- Decision is `match`: one invoice, full current balance and full line amount.
- Confidence is at least `AUTO_CONFIDENCE` (default 0.90).
- Positive line amount is at most `AUTO_LIMIT_CENTS` (default 500000, R 5 000,00).
- No risk flags.
- No linked `mismatch` proof, including documents claimed against the allocated invoice.
- The customer has at least one prior resolved case.

Server validation, current balances and policy are rechecked before the write. Confidence is a model assertion, not a calibrated probability. History does not certify identity. Never relax thresholds based solely on high synthetic accuracy.

## Review responsibilities

Read the actual bank amount/date/payer/reference and proposed invoice ownership. Inspect ordered tool evidence and similar cases; a precedent may be mistaken or stale. Check each outstanding balance, total allocations and remaining unapplied cents. For a split, confirm customer ownership and oldest-first order against the runbook. For duplicates, confirm the earlier settlement; for partial/excess payments, follow the fictional runbook and retain unapplied funds.

A proof verdict verifies a claim against the currently imported bank observations. It is not dispatch authorization, bank authenticity verification or permission to release goods. An unreadable/absent/mismatched claim requires independent investigation.

## Actions and overrides

**Approve (`A`)** applies the currently validated proposal once. A mismatch requires a nonempty note explaining the conflicting document and the independent bank evidence relied on. Approval of an escalation/duplicate records that resolution without allocations.

**Reject (`R`)** requires a note, records the original recommendation as rejected and escalates the line without allocations. It creates a masked retrievable case describing the rejection; it does not automatically rerun the agent.

**Correct** selects current open invoices, a decision and positive integer-cent allocations, with required rationale. The API rejects nonexistent invoices, overdrawing balances, exceeding bank cents and inconsistent decisions. The original proposal remains rejected; the corrected human resolution and allocations are authoritative. Overpayment surplus stays unapplied rather than increasing invoice balances.

All decisions record reviewer, note and authorization in an append-only audit. Repeated/stale review is rejected with 409. Invalid writes roll back atomically; refresh and inspect current evidence before retrying. Keyboard actions ignore editable inputs, repeated keys and modifier combinations.

Threshold changes require rerunning the full evaluation and checking automatic-allocation denominators, false allocations and safety invariants. A deployment beyond this synthetic demonstration requires authenticated roles and the business's actual approval authority.
