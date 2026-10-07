import { useEffect, useMemo, useState } from 'react';
import { ApiError, dateLabel, money, request } from './api';
import { Evidence } from './Evidence';
import { Icon } from './Icon';
import { ProofView } from './ProofView';
import { ReviewActions } from './ReviewActions';
import { useReview } from './useReview';
import type { Credentials, Decision, Resolution } from './types';

const decisionLabels: Record<Decision, string> = {
  match: 'Full match',
  partial: 'Partial payment',
  split: 'Split payment',
  overpayment: 'Overpayment',
  duplicate: 'Possible duplicate',
  escalate: 'Escalation',
};

function savedCredentials(): Credentials {
  try {
    return (
      JSON.parse(sessionStorage.getItem('clearline-reviewer') ?? 'null') ?? {
        apiKey: 'clearline-local-demo',
        reviewer: 'Demo Reviewer',
      }
    );
  } catch {
    return { apiKey: 'clearline-local-demo', reviewer: 'Demo Reviewer' };
  }
}

export default function App() {
  const review = useReview();
  const [view, setView] = useState<'review' | 'proof'>('review');
  const [tab, setTab] = useState<'overview' | 'evidence' | 'audit'>('overview');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [credentials, setCredentials] = useState<Credentials>(savedCredentials);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const visible = useMemo(
    () =>
      review.queue.filter(
        (p) =>
          (filter === 'all' || p.decision === filter) &&
          `${p.bank_line.payer_name} ${p.bank_line.raw_reference} ${decisionLabels[p.decision]}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [review.queue, filter, query],
  );
  const detail = review.detail?.id === review.selectedId ? review.detail : null;

  useEffect(() => {
    if (review.selectedId && !visible.some((p) => p.id === review.selectedId))
      review.setSelectedId(visible[0]?.id ?? null);
  }, [visible, review.selectedId, review.setSelectedId]);
  useEffect(() => {
    setTab('overview');
  }, [review.selectedId]);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 5500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function updateCredentials(next: Credentials) {
    setCredentials(next);
    sessionStorage.setItem('clearline-reviewer', JSON.stringify(next));
  }

  async function decide(action: 'approve' | 'reject', note: string, correction?: Resolution) {
    if (!detail || busy) return;
    setBusy(true);
    review.setError(null);
    try {
      await request(
        `/proposals/${detail.id}/${action}`,
        { method: 'POST', body: JSON.stringify({ note, corrected_resolution: correction }) },
        credentials,
      );
      setToast(
        correction
          ? 'Corrected resolution saved. The audit trail has been updated.'
          : action === 'approve'
            ? 'Proposal approved. Invoice balances have been updated.'
            : 'Proposal rejected and retained for investigation.',
      );
      await review.reload();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        await review.reload();
        review.setError('This proposal was already reviewed. The queue has been refreshed.');
      } else review.setError(e instanceof Error ? e.message : 'Could not save this decision.');
    } finally {
      setBusy(false);
    }
  }

  async function reconcile() {
    setBusy(true);
    review.setError(null);
    try {
      const result = await request<{
        agent_cases: number;
        rules: { matched: number; reversed: number };
      }>('/runs/reconcile', { method: 'POST' }, credentials);
      setToast(
        result.agent_cases || result.rules.matched || result.rules.reversed
          ? `Reconciled feed: ${result.rules.matched} exact matches, ${result.rules.reversed} reversals, ${result.agent_cases} investigations.`
          : 'The feed is up to date. No new bank lines need investigation.',
      );
      await review.reload();
    } catch (e) {
      review.setError(e instanceof Error ? e.message : 'Reconciliation failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="Clearline home">
          <span className="brand-mark">
            <i />
            <i />
            <i />
          </span>
          <span>
            clearline<span className="brand-dot">.</span>
          </span>
        </a>
        <div className="workspace-label">FINANCE WORKSPACE</div>
        <nav aria-label="Workspace">
          <button
            className={view === 'review' ? 'nav-item active' : 'nav-item'}
            onClick={() => setView('review')}
          >
            <Icon name="queue" />
            <span>Payment review</span>
            <span className="nav-count">{review.queue.length}</span>
          </button>
          <button
            className={view === 'proof' ? 'nav-item active' : 'nav-item'}
            onClick={() => setView('proof')}
          >
            <Icon name="proof" />
            <span>Payment proofs</span>
          </button>
        </nav>
        <div className="sidebar-principle">
          <span className="tiny-rule" />
          <h3>
            Evidence over
            <br />
            assumptions.
          </h3>
          <p>
            A proof is a claim.
            <br />
            The bank feed is the evidence.
          </p>
        </div>
        <div className="sidebar-bottom">
          <div className="environment-badge">
            <span className="status-dot" />
            Synthetic workspace
          </div>
          <span className="sidebar-small">ZAR · Africa/Johannesburg</span>
          <a
            href="http://localhost:18000/docs"
            target="_blank"
            rel="noreferrer"
            className="docs-link"
          >
            API reference <Icon name="external" size={13} />
          </a>
        </div>
      </aside>
      <main className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span>{' '}
            <strong>{view === 'review' ? 'Payment review' : 'Payment proofs'}</strong>
          </div>
          <div className="topbar-right">
            <span className="connection-state">
              <span className={`status-dot ${review.error ? 'offline' : ''}`} />
              {review.error
                ? 'Check connection'
                : review.metrics
                  ? 'Bank feed connected'
                  : 'Connecting…'}
            </span>
            <button
              className="reviewer-button"
              onClick={() => setSettingsOpen(!settingsOpen)}
              aria-expanded={settingsOpen}
            >
              <span className="avatar">
                {credentials.reviewer
                  .split(' ')
                  .map((n) => n[0])
                  .join('')
                  .slice(0, 2)
                  .toUpperCase()}
              </span>
              <span>{credentials.reviewer}</span>
              <Icon name="chevron" size={13} />
            </button>
          </div>
        </header>
        {settingsOpen && (
          <div className="reviewer-settings panel">
            <h3>Reviewer identity</h3>
            <p className="subtle">Used to attribute decisions in the audit trail.</p>
            <label>
              Reviewer
              <input
                value={credentials.reviewer}
                onChange={(e) => updateCredentials({ ...credentials, reviewer: e.target.value })}
              />
            </label>
            <label>
              Workspace API key
              <input
                type="password"
                autoComplete="off"
                value={credentials.apiKey}
                onChange={(e) => updateCredentials({ ...credentials, apiKey: e.target.value })}
              />
            </label>
            <button className="secondary-button full" onClick={() => setSettingsOpen(false)}>
              Done
            </button>
          </div>
        )}
        <div className="page-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">RECONCILIATION, WITH CONFIDENCE</span>
              <h1>
                {view === 'review'
                  ? 'Every payment. A clear decision.'
                  : 'Verify before you release.'}
              </h1>
              <p>
                {view === 'review'
                  ? 'Resolve exceptions with the evidence in front of you.'
                  : 'A polished PDF is no substitute for money in the bank.'}
              </p>
            </div>
            <div className="heading-actions">
              <button
                className="icon-button refresh-button"
                aria-label="Refresh queue"
                onClick={() => void review.reload()}
                disabled={busy}
              >
                <Icon name="refresh" />
              </button>
              {view === 'review' && (
                <button className="primary-button" onClick={() => void reconcile()} disabled={busy}>
                  <Icon name="bolt" />
                  {busy ? 'Working…' : 'Reconcile feed'}
                </button>
              )}
            </div>
          </div>
          {review.error && (
            <div className="error-banner" role="alert">
              <Icon name="info" />
              <span>{review.error}</span>
              <button className="text-button" onClick={() => void review.reload()}>
                Retry
              </button>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => review.setError(null)}
              >
                <Icon name="close" />
              </button>
            </div>
          )}
          {view === 'proof' ? (
            <ProofView credentials={credentials} />
          ) : (
            <>
              <section className="metrics-strip" aria-label="Reconciliation summary">
                <div className="metric">
                  <span>For your review</span>
                  <div>
                    <strong>{review.metrics ? review.queue.length : '—'}</strong>
                    <span className="metric-note amber">
                      <Icon name="clock" size={14} />
                      Human sign-off
                    </span>
                  </div>
                </div>
                <div className="metric">
                  <span>Matched bank lines</span>
                  <div>
                    <strong>{review.metrics?.bank_lines.matched ?? '—'}</strong>
                    <span className="metric-note">
                      <Icon name="check" size={14} />
                      Bank evidence
                    </span>
                  </div>
                </div>
                <div className="metric">
                  <span>Agent auto-applied</span>
                  <div>
                    <strong>{review.metrics?.proposals.auto_applied ?? '—'}</strong>
                    <span className="metric-note">
                      <Icon name="shield" size={14} />
                      Within policy
                    </span>
                  </div>
                </div>
                <div className="metric">
                  <span>Escalations</span>
                  <div>
                    <strong>{review.metrics?.bank_lines.escalated ?? '—'}</strong>
                    <span className="metric-note">Needs investigation</span>
                  </div>
                </div>
              </section>
              <div className="review-workspace">
                <section className="queue-panel panel" aria-label="Review queue">
                  <div className="queue-heading">
                    <h2>
                      Review queue <span>{visible.length}</span>
                    </h2>
                    <small>Highest amount first</small>
                  </div>
                  <div className="queue-filters">
                    <label className="search-input">
                      <Icon name="search" size={16} />
                      <input
                        aria-label="Search payments"
                        placeholder="Search payer or reference"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                      />
                    </label>
                    <select
                      aria-label="Filter by decision"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    >
                      <option value="all">All exceptions</option>
                      {Object.entries(decisionLabels).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="queue-list">
                    {review.loading ? (
                      <div className="queue-loading">
                        {[1, 2, 3, 4].map((n) => (
                          <div className="skeleton-card" key={n} />
                        ))}
                      </div>
                    ) : visible.length ? (
                      visible.map((p) => (
                        <button
                          key={p.id}
                          className={`queue-item ${p.id === review.selectedId ? 'selected' : ''}`}
                          onClick={() => review.setSelectedId(p.id)}
                          aria-pressed={p.id === review.selectedId}
                          disabled={busy}
                        >
                          <div className="queue-item-top">
                            <span className={`decision-label ${p.decision}`}>
                              {decisionLabels[p.decision]}
                            </span>
                            <span className="queue-confidence">
                              {Math.round(p.confidence * 100)}%
                            </span>
                          </div>
                          <strong className="queue-payer">{p.bank_line.payer_name}</strong>
                          <div className="queue-item-bottom">
                            <span className="mono queue-reference">
                              {p.bank_line.raw_reference || 'No payment reference'}
                            </span>
                            <span className="queue-amount">{money(p.bank_line.amount_cents)}</span>
                          </div>
                          <p>{p.policy_reason}</p>
                        </button>
                      ))
                    ) : (
                      <div className="queue-empty">
                        <Icon name="check" size={26} />
                        <h3>
                          {query || filter !== 'all' ? 'No matching exceptions' : 'All caught up'}
                        </h3>
                        <p>
                          {query || filter !== 'all'
                            ? 'Try a different payer, reference or decision.'
                            : 'New exceptions will appear here after reconciliation.'}
                        </p>
                      </div>
                    )}
                  </div>
                  <div className="queue-footer">
                    <span className="status-dot" />
                    Every proposal has an audit trail.
                  </div>
                </section>
                <section className="detail-panel panel" aria-label="Payment detail">
                  {review.detailLoading ? (
                    <div className="detail-loading">
                      <div className="skeleton-card" />
                      <div className="skeleton-card" />
                      <span>Loading bank evidence…</span>
                    </div>
                  ) : detail ? (
                    <>
                      <div className="detail-heading">
                        <div>
                          <span className="eyebrow">PAYMENT EXCEPTION</span>
                          <h2>{detail.bank_line.payer_name}</h2>
                        </div>
                        <span className={`decision-label ${detail.decision}`}>
                          {decisionLabels[detail.decision]}
                        </span>
                      </div>
                      <div className="detail-tabs" role="tablist" aria-label="Proposal evidence">
                        {(['overview', 'evidence', 'audit'] as const).map((t) => (
                          <button
                            key={t}
                            role="tab"
                            aria-selected={tab === t}
                            className={tab === t ? 'selected' : ''}
                            onClick={() => setTab(t)}
                          >
                            {t === 'audit' ? 'Audit trail' : t[0].toUpperCase() + t.slice(1)}
                            {t === 'evidence' && <span>{detail.steps}</span>}
                          </button>
                        ))}
                      </div>
                      <div className="detail-grid">
                        <div className="detail-body" role="tabpanel">
                          {tab === 'overview' ? (
                            <>
                              <section className="bank-observation">
                                <div className="section-heading">
                                  <span className="eyebrow">BANK OBSERVATION</span>
                                  <span className="subtle">
                                    {dateLabel(detail.bank_line.value_date)}
                                  </span>
                                </div>
                                <strong className="bank-amount">
                                  {money(detail.bank_line.amount_cents)}
                                </strong>
                                <div className="bank-fields">
                                  <div>
                                    <span>Payment reference</span>
                                    <strong className="mono untrusted-reference">
                                      {detail.bank_line.raw_reference || 'Not provided'}
                                    </strong>
                                  </div>
                                  <div>
                                    <span>Payer account</span>
                                    <strong className="mono">
                                      •••• {detail.bank_line.payer_account_masked}
                                    </strong>
                                  </div>
                                </div>
                              </section>
                              <section className="agent-reasoning">
                                <div className="section-heading">
                                  <h3>
                                    <Icon name="bolt" size={17} />
                                    Agent recommendation
                                  </h3>
                                  <span className="confidence-label">
                                    {Math.round(detail.confidence * 100)}% confidence
                                  </span>
                                </div>
                                <p>{detail.reasoning}</p>
                                {detail.risk_flags.length > 0 && (
                                  <div className="risk-flags">
                                    {detail.risk_flags.map((flag) => (
                                      <span key={flag}>
                                        <Icon name="shield" size={12} />
                                        {flag.replaceAll('_', ' ')}
                                      </span>
                                    ))}
                                  </div>
                                )}
                                <div className="confidence-track">
                                  <span style={{ width: `${detail.confidence * 100}%` }} />
                                </div>
                              </section>
                              <section className="allocations-section">
                                <div className="section-heading">
                                  <h3>Proposed allocation</h3>
                                  <span className="subtle">
                                    {detail.allocations.length} invoice
                                    {detail.allocations.length !== 1 ? 's' : ''}
                                  </span>
                                </div>
                                {detail.allocations.length ? (
                                  <table>
                                    <thead>
                                      <tr>
                                        <th>Invoice</th>
                                        <th>Allocation</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {detail.allocations.map((a, n) => (
                                        <tr key={a.invoice_number}>
                                          <td>
                                            <span className="invoice-number">
                                              {String(n + 1).padStart(2, '0')}
                                            </span>
                                            <span className="mono">{a.invoice_number}</span>
                                          </td>
                                          <td>{money(a.amount_cents)}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                    <tfoot>
                                      <tr>
                                        <td>Total proposed</td>
                                        <td>
                                          {money(
                                            detail.allocations.reduce(
                                              (sum, a) => sum + a.amount_cents,
                                              0,
                                            ),
                                          )}
                                        </td>
                                      </tr>
                                    </tfoot>
                                  </table>
                                ) : (
                                  <div className="no-allocation">
                                    <Icon name="shield" />
                                    <p>
                                      No allocation proposed. The received funds remain unapplied
                                      pending investigation.
                                    </p>
                                  </div>
                                )}
                                {detail.decision === 'overpayment' && (
                                  <p className="unapplied-note">
                                    Unapplied excess:{' '}
                                    <strong>
                                      {money(
                                        detail.bank_line.amount_cents -
                                          detail.allocations.reduce(
                                            (sum, a) => sum + a.amount_cents,
                                            0,
                                          ),
                                      )}
                                    </strong>
                                  </p>
                                )}
                              </section>
                              <section className="linked-proof">
                                <Icon name="proof" />
                                <div>
                                  <h3>Payment proof</h3>
                                  {detail.linked_pops?.length ? (
                                    detail.linked_pops.map((p) => (
                                      <p
                                        key={p.id}
                                        className={p.verdict === 'mismatch' ? 'form-error' : ''}
                                      >
                                        <strong>{p.verdict.replaceAll('_', ' ')}</strong> ·{' '}
                                        {p.summary}
                                      </p>
                                    ))
                                  ) : (
                                    <p>
                                      No document linked. The bank observation is the evidence of
                                      receipt.
                                    </p>
                                  )}
                                </div>
                              </section>
                              <div className="investigation-footer">
                                <Icon name="clock" size={14} />
                                <span>
                                  {detail.steps} tool steps · {detail.latency_ms} ms ·{' '}
                                  {detail.model.startsWith('stub')
                                    ? 'Scripted offline baseline'
                                    : detail.model}
                                </span>
                                <button className="text-button" onClick={() => setTab('evidence')}>
                                  Inspect evidence <Icon name="arrow" size={14} />
                                </button>
                              </div>
                            </>
                          ) : (
                            <Evidence detail={detail} audit={tab === 'audit'} />
                          )}
                        </div>
                        <ReviewActions detail={detail} busy={busy} onDecision={decide} />
                      </div>
                    </>
                  ) : (
                    <div className="detail-empty">
                      <Icon name="queue" size={38} />
                      <h2>
                        {review.error
                          ? 'Evidence is temporarily unavailable'
                          : 'Ready for a clearer decision.'}
                      </h2>
                      <p>
                        Select a payment from the queue to inspect its bank evidence, proposal and
                        audit trail.
                      </p>
                    </div>
                  )}
                </section>
              </div>
              <div className="workspace-footnote">
                <span>
                  <Icon name="shield" size={14} />
                  The model cannot write to the ledger. Automatic allocations pass deterministic
                  policy.
                </span>
                <span>All data is synthetic.</span>
              </div>
            </>
          )}
        </div>
      </main>
      {toast && (
        <div className="toast" role="status">
          <Icon name="check" />
          <span>{toast}</span>
          <button
            className="icon-button"
            aria-label="Dismiss notification"
            onClick={() => setToast(null)}
          >
            <Icon name="close" size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
