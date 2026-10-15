import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ApiError, money } from '../api';
import { Icon } from '../Icon';
import type { ProposalDetail, Resolution } from '../types';
import { useWorkspace } from '../workspace/Workspace';
import { usePreferences } from '../workspace/Preferences';
import { decisionLabels } from '../workspace/presentation';
import { PageHeader } from '../workspace/PageHeader';
import { ReconcileAction, Toast } from '../workspace/Feedback';
import { PaymentDetail, type DetailTab } from './PaymentDetail';

export function ReviewPage() {
  const { basePath, snapshot, request, reload, revision, mode } = useWorkspace();
  const { credentials } = usePreferences();
  const { proposalId } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const query = params.get('q') ?? '';
  const requestedFilter = params.get('decision') ?? 'all';
  const filter = Object.hasOwn(decisionLabels, requestedFilter) ? requestedFilter : 'all';
  const selectedTab = params.get('tab');
  const tab: DetailTab =
    selectedTab === 'evidence' || selectedTab === 'audit' ? selectedTab : 'overview';
  const [detail, setDetail] = useState<ProposalDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [reviewedId, setReviewedId] = useState<string | null>(null);
  const [implicitId, setImplicitId] = useState<string | null>(null);
  const selectedId = proposalId ?? implicitId;
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const visible = useMemo(
    () =>
      snapshot.queue.filter(
        (proposal) =>
          proposal.id !== reviewedId &&
          (filter === 'all' || proposal.decision === filter) &&
          `${proposal.bank_line.payer_name} ${proposal.bank_line.raw_reference} ${decisionLabels[proposal.decision]}`
            .toLowerCase()
            .includes(query.toLowerCase()),
      ),
    [snapshot.queue, filter, query, reviewedId],
  );
  function updateParam(name: string, value: string) {
    if (name === 'tab' && selectedId && !proposalId) {
      const next = new URLSearchParams(params);
      if (value === 'overview') next.delete('tab');
      else next.set('tab', value);
      navigate(`${basePath}/review/${selectedId}${next.size ? `?${next}` : ''}`);
      return;
    }
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        const isDefault =
          (name === 'decision' && value === 'all') || (name === 'tab' && value === 'overview');
        if (value && !isDefault) next.set(name, value);
        else next.delete(name);
        return next;
      },
      { replace: name !== 'tab' },
    );
  }
  function paymentPath(id: string) {
    const next = new URLSearchParams(params);
    next.delete('tab');
    return `${basePath}/review/${id}${next.size ? `?${next}` : ''}`;
  }
  useEffect(() => {
    if (!proposalId && !implicitId && !snapshot.loading && visible.length)
      setImplicitId(visible[0].id);
  }, [proposalId, implicitId, snapshot.loading, visible]);
  useEffect(() => {
    setError(null);
    if (!selectedId) {
      setDetail(null);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setDetail((previous) => (previous?.id === selectedId ? previous : null));
    setLoading(true);
    request<ProposalDetail>(`/proposals/${encodeURIComponent(selectedId)}`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setDetail(value);
      })
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(
            cause instanceof ApiError && cause.status === 404
              ? 'This payment was not found in this workspace. Choose another payment from the queue.'
              : cause instanceof Error
                ? cause.message
                : 'Could not load evidence.',
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [request, selectedId, revision]);
  async function decide(action: 'approve' | 'reject', note: string, correction?: Resolution) {
    if (!detail || busy) return;
    setBusy(true);
    setError(null);
    try {
      await request(
        `/proposals/${detail.id}/${action}`,
        { method: 'POST', body: JSON.stringify({ note, corrected_resolution: correction }) },
        credentials,
      );
      reload();
      if (!mounted.current) return;
      setReviewedId(detail.id);
      setImplicitId(null);
      setMessage(
        correction
          ? 'Corrected resolution saved. The audit trail has been updated.'
          : action === 'approve'
            ? 'Proposal approved. The resolution has been recorded.'
            : 'Proposal rejected and retained for investigation.',
      );
      navigate(`${basePath}/review${params.size ? `?${params}` : ''}`, { replace: true });
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) reload();
      if (mounted.current)
        setError(cause instanceof Error ? cause.message : 'Could not save the decision.');
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  const current = detail?.id === selectedId ? detail : null;
  return (
    <>
      <PageHeader
        eyebrow="Payment review"
        title="Make the call. With evidence."
        description="A focused queue. The full context. Your decision."
        actions={<ReconcileAction />}
      />
      {error && (
        <div className="error-banner" role="alert">
          <Icon name="info" />
          <p>{error}</p>
          <button className="secondary-button" onClick={reload}>
            Refresh evidence
          </button>
        </div>
      )}
      {mode === 'sample' && (
        <p className="sample-explainer">
          <Icon name="info" size={16} />
          Approvals and corrections are simulated here. Connected mode uses the actual policy and
          ledger.
        </p>
      )}
      <div className="review-workspace">
        <section className="queue-panel panel" aria-label="Review queue">
          <div className="queue-heading">
            <h2>
              Review queue <span className="neutral-badge">{visible.length}</span>
            </h2>
            <small>Highest amount first</small>
          </div>
          <div className="queue-filters">
            <label className="search-input">
              <Icon name="search" size={17} />
              <input
                aria-label="Search payments"
                placeholder="Payer or reference"
                value={query}
                onChange={(event) => updateParam('q', event.target.value)}
              />
            </label>
            <select
              aria-label="Filter by decision"
              value={filter}
              onChange={(event) => updateParam('decision', event.target.value)}
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
            {snapshot.loading ? (
              <div className="queue-loading">
                {[1, 2, 3].map((number) => (
                  <div className="skeleton-card" key={number} />
                ))}
              </div>
            ) : visible.length ? (
              visible.map((proposal) => (
                <Link
                  className={`queue-item ${proposal.id === selectedId ? 'selected' : ''} ${busy ? 'disabled' : ''}`}
                  key={proposal.id}
                  to={paymentPath(proposal.id)}
                  aria-current={proposal.id === selectedId ? 'true' : undefined}
                  onClick={(event) => {
                    if (busy) event.preventDefault();
                  }}
                >
                  <div className="queue-item-top">
                    <span className={`decision-label ${proposal.decision}`}>
                      {decisionLabels[proposal.decision]}
                    </span>
                    <span className="queue-confidence">
                      {Math.round(proposal.confidence * 100)}%
                    </span>
                  </div>
                  <strong className="queue-payer">{proposal.bank_line.payer_name}</strong>
                  <div className="queue-item-bottom">
                    <span className="queue-reference mono">
                      {proposal.bank_line.raw_reference || 'No reference'}
                    </span>
                    <span className="queue-amount">{money(proposal.bank_line.amount_cents)}</span>
                  </div>
                  <p>{proposal.policy_reason}</p>
                </Link>
              ))
            ) : (
              <div className="queue-empty">
                <Icon name="check" size={27} />
                <h3>
                  {query || filter !== 'all'
                    ? 'No matching payments'
                    : snapshot.error
                      ? 'Queue unavailable'
                      : 'All caught up'}
                </h3>
                <p>
                  {query || filter !== 'all'
                    ? 'Try a different search or decision.'
                    : snapshot.error
                      ? 'Connect to the API or explore the sample workspace.'
                      : 'New exceptions appear after reconciliation.'}
                </p>
                {(query || filter !== 'all') && (
                  <button className="text-button" onClick={() => setParams({})}>
                    Clear filters
                  </button>
                )}
              </div>
            )}
          </div>
          <div className="queue-footer">
            <Icon name="shield" size={14} />
            Every proposal has an audit trail.
          </div>
        </section>
        <section className="detail-panel panel" aria-label="Payment detail">
          {current ? (
            <PaymentDetail
              detail={current}
              busy={busy}
              decide={decide}
              tab={tab}
              setTab={(value) => updateParam('tab', value)}
            />
          ) : loading ? (
            <div className="detail-loading">
              <div className="skeleton-card" />
              <p>Loading bank evidence…</p>
            </div>
          ) : (
            <div className="detail-empty">
              <Icon name={error ? 'search' : 'queue'} size={36} />
              <h2>{error ? 'Payment unavailable' : 'Ready for a clearer decision.'}</h2>
              <p>{error ?? 'Select a payment to inspect its proposal and audit trail.'}</p>
            </div>
          )}
        </section>
      </div>
      <Toast message={message} clear={() => setMessage(null)} />
    </>
  );
}
