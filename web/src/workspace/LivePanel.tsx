import { Link } from 'react-router-dom';
import { Icon } from '../Icon';
import { money } from '../api';
import { useWorkspace } from './Workspace';
import { clockLabel, eventLabels } from './presentation';

export function LivePanel({ expanded = false }: { expanded?: boolean }) {
  const { mode, basePath, snapshot, polling, setPolling, reload } = useWorkspace();
  const sample = mode === 'sample';
  const provider = snapshot.metrics?.provider;
  const providerName =
    provider === 'stub'
      ? 'Scripted agent · offline'
      : provider === 'sample'
        ? 'Illustrated investigation'
        : provider === 'claude'
          ? 'Claude'
          : provider === 'mimo'
            ? 'MiMo'
            : 'Awaiting API';
  return (
    <section className={`live-panel panel ${expanded ? 'expanded' : ''}`} aria-label="Live panel">
      <div className="section-heading">
        <h2>
          <Icon name="activity" size={20} />
          Live panel
        </h2>
        <span
          className={`status-badge ${sample ? 'sample' : snapshot.error ? 'unsafe' : snapshot.updatedAt && polling ? 'success' : 'neutral'}`}
        >
          <span className="status-dot" />
          {sample
            ? 'Simulated'
            : snapshot.error
              ? 'Offline'
              : !polling
                ? 'Paused'
                : snapshot.updatedAt
                  ? 'Connected'
                  : 'Connecting'}
        </span>
      </div>
      <p className="live-description">
        {sample
          ? 'A preview of the events you’ll see as payments move through review.'
          : 'Actual API health, agent configuration and audited workspace activity.'}
      </p>
      <div className="connection-details">
        <div>
          <span>Source</span>
          <strong>{sample ? 'Browser-only sample' : 'Clearline API'}</strong>
        </div>
        <div>
          <span>Agent</span>
          <strong>{providerName}</strong>
        </div>
        <div>
          <span>Updates</span>
          <strong>
            {sample ? 'After sample actions' : polling ? 'Every 10 seconds' : 'Paused'}
          </strong>
        </div>
      </div>
      <div className="activity-heading">
        <h3>{sample ? 'Sample activity' : 'Latest activity'}</h3>
        {!expanded && (
          <Link to={`${basePath}/activity`} aria-label="View all activity">
            <Icon name="arrow" size={18} />
          </Link>
        )}
      </div>
      <div className="activity-list">
        {snapshot.loading ? (
          <p className="subtle">Loading workspace events…</p>
        ) : snapshot.activity.length ? (
          snapshot.activity.slice(0, expanded ? 20 : 4).map((event) => (
            <article className="activity-item" key={event.id}>
              <span className="activity-icon">
                <Icon
                  name={
                    event.event_type.includes('pop')
                      ? 'proof'
                      : event.event_type.includes('human')
                        ? 'check'
                        : 'shield'
                  }
                  size={16}
                />
              </span>
              <div>
                <strong>
                  {eventLabels[event.event_type] ?? event.event_type.replaceAll('_', ' ')}
                </strong>
                <p>
                  {event.payer_name ?? event.actor}
                  {expanded && event.amount_cents !== null ? ` · ${money(event.amount_cents)}` : ''}
                </p>
                {expanded && (
                  <small>
                    {event.actor} ·{' '}
                    {new Intl.DateTimeFormat('en-ZA', {
                      dateStyle: 'medium',
                      timeZone: 'Africa/Johannesburg',
                    }).format(new Date(event.created_at))}
                  </small>
                )}
                {expanded && event.proposal_id && (
                  <Link
                    className="activity-trace-link"
                    to={`${basePath}/review/${event.proposal_id}?tab=audit`}
                  >
                    Inspect audit trail <Icon name="arrow" size={13} />
                  </Link>
                )}
              </div>
              <time dateTime={event.created_at}>{clockLabel(event.created_at)}</time>
            </article>
          ))
        ) : (
          <div className="empty-inline">
            <Icon name="clock" />
            <p>
              {snapshot.error
                ? 'Connect to the API to load audited events.'
                : 'No decisions yet. Reconcile an imported feed to begin.'}
            </p>
          </div>
        )}
      </div>
      <div className="live-footer">
        <span>
          {snapshot.updatedAt
            ? `${sample ? 'Preview loaded' : snapshot.error ? 'Last successful sync' : 'Last synced'} ${clockLabel(snapshot.updatedAt)}`
            : 'No successful sync yet'}
          <small>Africa/Johannesburg</small>
        </span>
        {!sample && (
          <div className="live-controls">
            <button
              className="icon-button"
              aria-label={polling ? 'Pause live updates' : 'Resume live updates'}
              onClick={() => setPolling(!polling)}
            >
              <Icon name={polling ? 'pause' : 'play'} size={16} />
            </button>
            <button
              className="icon-button"
              aria-label="Refresh live panel"
              onClick={reload}
              disabled={snapshot.refreshing}
            >
              <Icon name="refresh" size={16} />
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
