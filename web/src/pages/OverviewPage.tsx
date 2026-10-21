import { Link } from 'react-router-dom';
import { Icon } from '../Icon';
import { money } from '../api';
import { useWorkspace } from '../workspace/Workspace';
import { LivePanel } from '../workspace/LivePanel';
import { PageHeader } from '../workspace/PageHeader';
import { ReconcileAction } from '../workspace/Feedback';
import { decisionLabels } from '../workspace/presentation';

export function OverviewPage() {
  const { mode, basePath, snapshot, resetSample } = useWorkspace();
  const total = snapshot.bankLines.reduce((sum, line) => sum + line.amount_cents, 0);
  const matched = snapshot.metrics?.bank_lines.matched ?? 0;
  const riskCases = snapshot.queue.filter((proposal) => proposal.risk_flags.length > 0).length;
  const auto = snapshot.metrics?.proposals.auto_applied ?? 0;
  const reviewValue = snapshot.queue.reduce(
    (sum, proposal) => sum + proposal.bank_line.amount_cents,
    0,
  );
  return (
    <>
      <PageHeader
        eyebrow="A little clarity goes a long way"
        title="Every payment. In perspective."
        description="See what’s settled, what needs you, and the evidence behind it."
        actions={
          mode === 'sample' ? (
            <button className="secondary-button" onClick={resetSample}>
              <Icon name="refresh" size={16} />
              Reset sample
            </button>
          ) : (
            <ReconcileAction />
          )
        }
      />
      <div className="overview-grid">
        <div className="overview-main">
          <section className="balance-card panel" aria-label="Imported transfer summary">
            <div className="section-heading">
              <span className="eyebrow">Net imported transfers</span>
              <span className="neutral-badge">ZAR</span>
            </div>
            <div className={`balance-value ${snapshot.loading ? 'loading-value' : ''}`}>
              {snapshot.loading || (!snapshot.metrics && snapshot.error) ? '—' : money(total)}
            </div>
            <p className="balance-caption">
              {snapshot.bankLines.length.toLocaleString('en-ZA')} loaded bank observations. Not an
              account balance.
            </p>
            <div className="balance-divider" />
            <div className="summary-stats">
              <div>
                <span className="stat-icon">
                  <Icon name="check" size={18} />
                </span>
                <strong>{snapshot.metrics ? matched : '—'}</strong>
                <span>Matched bank lines</span>
              </div>
              <div>
                <span className="stat-icon">
                  <Icon name="shield" size={18} />
                </span>
                <strong>{snapshot.metrics ? auto : '—'}</strong>
                <span>Agent auto-applied</span>
              </div>
              <div>
                <span className="stat-icon">
                  <Icon name="clock" size={18} />
                </span>
                <strong>{snapshot.metrics ? snapshot.queue.length : '—'}</strong>
                <span>For your review</span>
              </div>
            </div>
          </section>
          <section className="review-preview panel" aria-label="Priority payment reviews">
            <div className="section-heading">
              <div>
                <h2>A few need your eye.</h2>
                <p className="subtle">
                  {snapshot.metrics
                    ? `${money(reviewValue)} awaiting a decision.`
                    : 'Load a workspace to see pending decisions.'}
                </p>
              </div>
              <Link className="text-link" to={`${basePath}/review`}>
                Review all <Icon name="arrow" size={16} />
              </Link>
            </div>
            {snapshot.loading ? (
              <div className="skeleton-card" />
            ) : snapshot.queue.length ? (
              snapshot.queue.slice(0, 4).map((proposal) => (
                <Link
                  className="preview-row"
                  key={proposal.id}
                  to={`${basePath}/review/${proposal.id}`}
                >
                  <span className="payer-avatar">
                    {proposal.bank_line.payer_name
                      .split(' ')
                      .map((word) => word[0])
                      .slice(0, 2)
                      .join('')}
                  </span>
                  <div className="preview-payer">
                    <strong>{proposal.bank_line.payer_name}</strong>
                    <span>{decisionLabels[proposal.decision]}</span>
                  </div>
                  <span className="preview-amount">{money(proposal.bank_line.amount_cents)}</span>
                  <Icon name="chevron" size={15} />
                </Link>
              ))
            ) : (
              <div className="empty-inline">
                <Icon name="check" />
                <p>
                  {snapshot.error
                    ? 'Connect the workspace to load the queue.'
                    : 'All caught up. New exceptions appear after reconciliation.'}
                </p>
              </div>
            )}
          </section>
          <Link className="proof-prompt panel" to={`${basePath}/proofs`}>
            <span className="proof-prompt-icon">
              <Icon name="proof" size={28} />
            </span>
            <div>
              <h2>A claim isn’t a clearance.</h2>
              <p>Check the bank evidence before you release goods.</p>
            </div>
            <span className="text-link">
              Verify a proof <Icon name="arrow" size={17} />
            </span>
          </Link>
        </div>
        <div className="overview-aside">
          <LivePanel />
          <section className="assurance-card">
            <Icon name="shield" size={22} />
            <h3>Careful by design.</h3>
            <p>
              {riskCases} pending {riskCases === 1 ? 'case carries' : 'cases carry'} a risk flag.
              The agent cannot write to the ledger.
            </p>
            <Link to={`${basePath}/settings`}>
              View workspace safeguards <Icon name="arrow" size={14} />
            </Link>
          </section>
          <section className="workspace-resources panel" aria-label="Workspace resources">
            <Link to={`${basePath}/import`}>
              <Icon name="upload" size={20} />
              <span>
                <strong>Bring in your records</strong>
                <small>CSV templates, validation and imports.</small>
              </span>
              <Icon name="chevron" size={15} />
            </Link>
            <Link to={`${basePath}/evaluation`}>
              <Icon name="shield" size={20} />
              <span>
                <strong>Inspect the evidence</strong>
                <small>Measured runs, release gates and limits.</small>
              </span>
              <Icon name="chevron" size={15} />
            </Link>
          </section>
        </div>
      </div>
    </>
  );
}
