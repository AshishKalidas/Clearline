# Failure modes

The platform is designed to withhold unsafe allocations, but confidence, past cases and a synthetic evaluation cannot guarantee correctness on new inputs.

| Failure | Detection | Ledger boundary / next action |
|---|---|---|
| Two plausible invoices with the same balance | Multiple candidates; prompt requires ambiguity escalation | No guessed match; reviewer investigates customer intent |
| Look-alike customers or mistyped payer | Fuzzy scores and candidate evidence | Fuzzy identity is evidence only; unfamiliar customers lack auto history; reviewer checks ownership |
| Reference points at the wrong invoice | Customer/amount evidence conflicts with reference | Agent proposes evidence-based correction; balances and policy still validate |
| Injected instructions in references/tool data | Delimited untrusted context, explicit prompt rules, fixture injection gate | No executable SQL/write tools; suspicious references bypass exact rules; risk flags veto auto application |
| Hallucinated invoice, bad cents or inconsistent decision | Typed arguments and server proposal validation | Structured error; second invalid terminal attempt escalates; no allocation |
| Unsupported evidence citation | Citation must name a successful actual tool call | Invalid terminal proposal is rejected; citation existence alone does not prove semantic correctness |
| Provider outage, malformed replies or throttling | SDK retries/timeouts, outer deadline and missing-terminal checks | Escalation with reason; evaluations fail incomplete-investigation gate |
| Agent loops or excessive tool calls | Eight-call and 60-second limits; bounded database statements | Fail-safe escalation; no partial model allocation |
| Prior case is stale or wrong | Current/reversed cases excluded; customer filter; balances re-read | Retrieval is advisory; current evidence and validation remain required |
| Mixed embedding spaces / unavailable local model | Local cache load fails explicitly; report identifies embedder | Use the hash demo or pre-cache/reindex a fresh corpus; never mix indexes |
| Concurrent review or invoice already settled | Transaction locks, proposal status check, current-balance validation | Atomic rollback; repeated review returns 409; no duplicate allocation |
| Duplicate transfer | Same payer/amount and settled history within seven days | No new allocation; reviewer handles the duplicate; no refunds are sent |
| Excess or short payment | Cents conservation and decision/cardinality checks | Surplus stays unapplied; shortfalls/splits require human sign-off |
| Unattributable or ambiguous reversal | Unique amount/payer/reference match within ten days required | Rules do not unwind a guessed transfer; unresolved negative lines escalate |
| Edited amount/date/reference/beneficiary on a PDF | Independent field checks against bank feed | Mismatch blocks rules and agent auto; explained human override only |
| Claim without received funds | No related positive bank observation | `not_received`; do not release goods |
| Scanned/encrypted/broken/unseen PDF layout | Required fields absent or extraction failure | `unreadable`; no OCR inference or automatic clearance |
| Delayed/incomplete bank feed | The system can only inspect imported observations | Absent payment is provisional until bank data is refreshed; never treat a PDF as replacement evidence |
| A later PDF conflicts with an already settled line | Stored mismatch appears in linked evidence | Future automatic writes are blocked; historical settlements are not silently unwound; reviewer investigates |
| Unrecognized PII pattern | Outbound pattern tests cover only documented classes | Synthetic-only deployment; regex redaction is not complete anonymization |

The demonstration serializes mutations and processes reconciliation in one request/transaction. A large batch with live providers can take a long time and hold a lock. A production implementation needs durable jobs, cancellation/retry semantics, stronger identity, tenant boundaries and operational monitoring; those are outside this PRD. PDF extraction is bounded by file size and pages, but it is not an isolated hostile-document sandbox.

The independent mismatch invariant is conservative: it flags existing non-human allocations if conflicting proof evidence is subsequently added. It is useful for investigation; it does not reverse historical funds on upload. Evaluate clean, isolated fixtures to distinguish release behavior from a changed operational evidence set.
