import { Icon } from '../Icon';
import { money, dateLabel } from '../api';
import { Evidence } from '../Evidence';
import { ReviewActions, type ReviewActionsProps } from '../ReviewActions';
import type { ProposalDetail } from '../types';
import { useWorkspace } from '../workspace/Workspace';
import { decisionLabels } from '../workspace/presentation';
export type DetailTab = 'overview' | 'evidence' | 'audit';
export function PaymentDetail({
  detail,
  busy,
  decide,
  tab,
  setTab,
}: {
  detail: ProposalDetail;
  busy: boolean;
  decide: ReviewActionsProps['onDecision'];
  tab: DetailTab;
  setTab: (tab: DetailTab) => void;
}) {
  const { mode } = useWorkspace();
  return (
    <>
      <div className="detail-heading">
        <div>
          <span className="eyebrow">Payment exception</span>
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
                  <span className="eyebrow">Bank observation</span>
                  <span className="subtle">{dateLabel(detail.bank_line.value_date)}</span>
                </div>
                <strong className="bank-amount">{money(detail.bank_line.amount_cents)}</strong>
                <div className="bank-fields">
                  <div>
                    <span>Payment reference</span>
                    <strong className="mono untrusted-reference">
                      {detail.bank_line.raw_reference || 'Not provided'}
                    </strong>
                  </div>
                  <div>
                    <span>Payer account</span>
                    <strong className="mono">•••• {detail.bank_line.payer_account_masked}</strong>
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
                            <span className="invoice-number">{String(n + 1).padStart(2, '0')}</span>
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
                          {money(detail.allocations.reduce((sum, a) => sum + a.amount_cents, 0))}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                ) : (
                  <div className="no-allocation">
                    <Icon name="shield" />
                    <p>
                      No allocation proposed. The received funds remain unapplied pending
                      investigation.
                    </p>
                  </div>
                )}
                {detail.decision === 'overpayment' && (
                  <p className="unapplied-note">
                    Unapplied excess:{' '}
                    <strong>
                      {money(
                        detail.bank_line.amount_cents -
                          detail.allocations.reduce((sum, a) => sum + a.amount_cents, 0),
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
                      <p key={p.id} className={p.verdict === 'mismatch' ? 'form-error' : ''}>
                        <strong>{p.verdict.replaceAll('_', ' ')}</strong> · {p.summary}
                      </p>
                    ))
                  ) : (
                    <p>No document linked. The bank observation is the evidence of receipt.</p>
                  )}
                </div>
              </section>
              <div className="investigation-footer">
                <Icon name="clock" size={14} />
                <span>
                  {mode === 'sample'
                    ? 'Illustrated tool evidence · '
                    : `${detail.steps} tool steps · ${detail.latency_ms} ms · `}
                  {mode === 'sample'
                    ? 'Sample preview'
                    : detail.model.startsWith('stub')
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
        {detail.status === 'pending' ? (
          <ReviewActions detail={detail} busy={busy} onDecision={decide} />
        ) : (
          <aside className="review-panel resolved-notice">
            <Icon name="check" size={28} />
            <h3>Already reviewed</h3>
            <p>
              This proposal is {detail.status.replaceAll('_', ' ')}. The audit trail preserves the
              decision.
            </p>
            {detail.reviewer && <strong>{detail.reviewer}</strong>}
            {detail.review_note && <p>{detail.review_note}</p>}
          </aside>
        )}
      </div>
    </>
  );
}
