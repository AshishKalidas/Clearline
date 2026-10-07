import { Icon } from './Icon';
import { money } from './api';
import type { AuditEvent, Invoice, ProposalDetail } from './types';

const toolNames: Record<string, string> = {
  find_customers: 'Customer identity',
  search_invoices: 'Open invoice search',
  find_duplicate_candidates: 'Duplicate payment check',
  find_similar_cases: 'Similar resolved cases',
  search_runbook: 'Reconciliation policy',
  get_invoice: 'Invoice history',
  get_customer: 'Customer payment behavior',
  get_payment_history: 'Prior payments',
  get_pop_verification: 'Payment proof verification',
  submit_proposal: 'Validated proposal',
};

function ToolResult({ event }: { event: AuditEvent }) {
  const result = event.payload.result;
  if (Array.isArray(result) && event.payload.tool === 'search_invoices') {
    return (
      <div className="evidence-invoices">
        {(result as Invoice[]).map((i) => (
          <div key={i.id}>
            <span className="mono">{i.invoice_number}</span>
            <span>{money(i.outstanding_cents)}</span>
          </div>
        ))}
      </div>
    );
  }
  if (Array.isArray(result) && event.payload.tool === 'find_customers') {
    return (
      <div>
        {result.length ? (
          result.map((c: { id: string; name: string; account_code: string; score: number }) => (
            <div className="evidence-customer" key={c.id}>
              <strong>{c.name}</strong>
              <span className="mono">
                {c.account_code} · {Math.round(c.score * 100)}% similarity
              </span>
            </div>
          ))
        ) : (
          <p>No plausible customer found.</p>
        )}
      </div>
    );
  }
  if (Array.isArray(result) && event.payload.tool === 'find_similar_cases') {
    return (
      <div>
        {result.length ? (
          result.map((c: { id: string; summary: string; resolved_by: string }) => (
            <div className="past-case" key={c.id}>
              <p>{c.summary}</p>
              <small>Resolved by {c.resolved_by.replaceAll('_', ' ')}</small>
            </div>
          ))
        ) : (
          <p>No prior cases retrieved for this investigation.</p>
        )}
      </div>
    );
  }
  if (Array.isArray(result) && event.payload.tool === 'search_runbook') {
    return (
      <div>
        {result.length ? (
          result.map((c: { id: string; section: string; text: string }) => (
            <details className="runbook-section" key={c.id}>
              <summary>{c.section}</summary>
              <p>{c.text}</p>
            </details>
          ))
        ) : (
          <p>No policy sections retrieved.</p>
        )}
      </div>
    );
  }
  if (event.payload.tool === 'find_duplicate_candidates' && Array.isArray(result) && !result.length)
    return <p>No equal prior settled payment was found within seven days.</p>;
  return (
    <details className="raw-evidence">
      <summary>Inspect observed result</summary>
      <pre>{JSON.stringify(result, null, 2)}</pre>
    </details>
  );
}

export function Evidence({ detail, audit = false }: { detail: ProposalDetail; audit?: boolean }) {
  const events = audit ? detail.trace : detail.trace.filter((e) => e.event_type === 'tool_call');
  return (
    <section
      className="evidence-list"
      aria-label={audit ? 'Audit trail' : 'Investigation evidence'}
    >
      <div className="section-heading">
        <h3>{audit ? 'Every decision, recorded.' : 'The evidence behind the proposal'}</h3>
        <span className="subtle">
          {events.length} {audit ? 'events' : 'steps'}
        </span>
      </div>
      {events.map((event, index) => (
        <article className="evidence-event" key={event.id}>
          <div className="step-marker">
            {audit ? <Icon name="clock" size={14} /> : (event.payload.step ?? index + 1)}
          </div>
          <div className="evidence-body">
            <div className="evidence-title">
              <strong>
                {audit
                  ? event.event_type.replaceAll('_', ' ')
                  : (toolNames[event.payload.tool ?? ''] ?? event.payload.tool)}
              </strong>
              <span className="mono subtle">{audit ? event.actor : event.payload.citation}</span>
            </div>
            {audit ? (
              <>
                <small>
                  {new Intl.DateTimeFormat('en-ZA', {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                    timeZone: 'Africa/Johannesburg',
                  }).format(new Date(event.created_at))}
                </small>
                <details className="raw-evidence">
                  <summary>Inspect audit payload</summary>
                  <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                </details>
              </>
            ) : (
              <ToolResult event={event} />
            )}
          </div>
        </article>
      ))}
    </section>
  );
}
