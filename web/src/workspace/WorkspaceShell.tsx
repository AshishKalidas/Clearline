import { useEffect } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { Icon, type IconName } from '../Icon';
import { isDemoDeployment } from '../deployment';
import { usePreferences } from './Preferences';
import { useWorkspace } from './Workspace';

const destinations: { path: string; label: string; short: string; icon: IconName }[] = [
  { path: 'overview', label: 'Overview', short: 'Overview', icon: 'home' },
  { path: 'review', label: 'Payment review', short: 'Review', icon: 'queue' },
  { path: 'proofs', label: 'Payment proofs', short: 'Proofs', icon: 'proof' },
  { path: 'activity', label: 'Activity', short: 'Activity', icon: 'activity' },
  { path: 'settings', label: 'Settings', short: 'Settings', icon: 'settings' },
];
export function WorkspaceShell() {
  const { mode, basePath, snapshot, reload } = useWorkspace();
  const { credentials } = usePreferences();
  const { pathname } = useLocation();
  const section = pathname.split('/')[2] ?? 'overview';
  const current = destinations.find((item) => item.path === section);
  const auxiliary =
    section === 'import'
      ? 'Data imports'
      : section === 'evaluation'
        ? 'Evaluation evidence'
        : undefined;
  const label = current?.label ?? auxiliary ?? 'Page not found';
  useEffect(() => {
    document.title = `${label} · ${mode === 'sample' ? 'Sample' : 'Connected'} · Clearline`;
    document.getElementById('workspace-main')?.focus({ preventScroll: true });
    window.scrollTo({ top: 0 });
  }, [section, mode, label]);
  const destination = current?.path ?? (auxiliary ? section : 'overview');
  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace-main">
        Skip to content
      </a>
      <aside className="sidebar glass" aria-label="Workspace navigation">
        <Link className="brand" to={`${basePath}/overview`} aria-label="Clearline home">
          <span className="brand-symbol">
            <i />
            <i />
            <i />
          </span>
          <span>Clearline</span>
        </Link>
        <div className="workspace-label">Your workspace</div>
        <nav aria-label="Workspace">
          {destinations.map((item) => (
            <NavLink
              key={item.path}
              to={`${basePath}/${item.path}`}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon name={item.icon} size={20} />
              <span className="nav-label">{item.label}</span>
              <span className="nav-short">{item.short}</span>
              {item.path === 'review' && snapshot.queue.length > 0 && (
                <span className="nav-count">{snapshot.queue.length}</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="workspace-avatar">
            <Icon name="layers" size={23} />
          </div>
          <strong>{mode === 'sample' ? 'Sample workspace' : 'Connected workspace'}</strong>
          <p>{mode === 'sample' ? 'A safe place to explore.' : 'Your local API and ledger.'}</p>
          <span className="sidebar-meta">Synthetic data · ZAR</span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar glass">
          <div className="breadcrumb">
            <span>Workspace</span>
            <Icon name="chevron" size={12} />
            <strong>{label}</strong>
          </div>
          <nav className="mode-switch" aria-label="Workspace mode">
            <Link
              className={mode === 'sample' ? 'selected' : ''}
              aria-current={mode === 'sample' ? 'true' : undefined}
              to={`/sample/${destination}`}
              aria-label="Sample workspace"
            >
              <Icon name="layers" size={15} />
              Sample
            </Link>
            {!isDemoDeployment() && (
              <Link
                className={mode === 'connected' ? 'selected' : ''}
                aria-current={mode === 'connected' ? 'true' : undefined}
                to={`/workspace/${destination}`}
                aria-label="Connected workspace"
              >
                <Icon name="activity" size={15} />
                Connected
              </Link>
            )}
          </nav>
          <Link
            to={`${basePath}/settings`}
            className="reviewer-button"
            aria-label="Reviewer settings"
          >
            <span className="avatar">
              {credentials.reviewer
                .split(' ')
                .filter(Boolean)
                .map((word) => word[0])
                .join('')
                .slice(0, 2)
                .toUpperCase() || 'DR'}
            </span>
          </Link>
        </header>
        <main id="workspace-main" className="page-content" tabIndex={-1}>
          <div className={`workspace-context ${mode}`}>
            <span className="context-label">
              <span className="status-dot" />
              {mode === 'sample' ? 'Sample workspace' : 'Connected workspace'}
            </span>
            <span>
              {mode === 'sample'
                ? 'Illustrative data. Changes stay in this preview.'
                : 'API-backed data. All supplied bank records are synthetic.'}
            </span>
          </div>
          {snapshot.error && (
            <div className="error-banner" role="alert">
              <Icon name="info" />
              <div>
                <strong>Workspace connection unavailable</strong>
                <p>
                  {snapshot.error}
                  {snapshot.updatedAt ? ' Showing the last successful snapshot.' : ''}
                </p>
              </div>
              <button className="secondary-button" onClick={reload}>
                Retry
              </button>
              <Link to="/sample/overview">Explore sample</Link>
            </div>
          )}
          <Outlet />
          <footer className="workspace-footnote">
            <span>
              <Icon name="shield" size={15} />
              The agent proposes. Policy and people decide.
            </span>
            <span>Clearline · Evidence first.</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
