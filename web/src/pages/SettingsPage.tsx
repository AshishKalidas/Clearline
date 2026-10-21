import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon, type IconName } from '../Icon';
import { isDemoDeployment } from '../deployment';
import { useWorkspace } from '../workspace/Workspace';
import { usePreferences, type Appearance } from '../workspace/Preferences';
import { PageHeader } from '../workspace/PageHeader';

const themes: { value: Appearance; label: string; icon: IconName }[] = [
  { value: 'light', label: 'Light', icon: 'sun' },
  { value: 'dark', label: 'Dark', icon: 'moon' },
  { value: 'system', label: 'System', icon: 'monitor' },
];
export function SettingsPage() {
  const { mode, basePath, snapshot, resetSample } = useWorkspace();
  const { credentials, saveCredentials, appearance, setAppearance } = usePreferences();
  const [reviewer, setReviewer] = useState(credentials.reviewer);
  const [apiKey, setApiKey] = useState(credentials.apiKey);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <PageHeader
        eyebrow="Make yourself at home"
        title="Your workspace. Your way."
        description="A few thoughtful settings. The same careful safeguards."
      />
      <div className="settings-grid">
        <div>
          <section className="settings-card panel workspace-tools">
            <h2>Keep the evidence close.</h2>
            <p>
              Import records with a preview, or inspect the platform’s published evaluation reports.
            </p>
            <Link className="text-link" to={`${basePath}/import`}>
              Data imports <Icon name="arrow" size={15} />
            </Link>
            <Link className="text-link" to={`${basePath}/evaluation`}>
              Evaluation evidence <Icon name="arrow" size={15} />
            </Link>
          </section>
          <section className="settings-card panel">
            <div className="section-heading">
              <h2>Reviewer identity</h2>
              <Icon name="edit" size={20} />
            </div>
            <p className="subtle">Attribute every decision to the person making it.</p>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                if (!reviewer.trim()) {
                  setError('Enter a reviewer name.');
                  return;
                }
                saveCredentials({ reviewer: reviewer.trim(), apiKey });
                setSaved(true);
                setError(null);
              }}
            >
              <label>
                Reviewer name
                <input
                  value={reviewer}
                  maxLength={100}
                  onChange={(event) => {
                    setReviewer(event.target.value);
                    setSaved(false);
                  }}
                  required
                  autoComplete="nickname"
                />
              </label>
              {mode === 'connected' && (
                <label>
                  Workspace API key
                  <input
                    type="password"
                    autoComplete="off"
                    value={apiKey}
                    onChange={(event) => {
                      setApiKey(event.target.value);
                      setSaved(false);
                    }}
                  />
                  <small>Sent only with actions that change the connected workspace.</small>
                </label>
              )}
              <p className="settings-help">
                Identity and API key are kept in this tab’s session storage. This demonstration does
                not provide production authentication.
              </p>
              {error && (
                <p role="alert" className="form-error">
                  {error}
                </p>
              )}
              <div className="save-row">
                <button className="primary-button" type="submit">
                  Save preferences
                </button>
                {saved && (
                  <span className="saved-label" role="status">
                    <Icon name="check" size={17} />
                    Saved
                  </span>
                )}
              </div>
            </form>
          </section>
          <section className="settings-card panel">
            <h2>Appearance</h2>
            <p className="subtle">Follow your device, or choose a look that feels right.</p>
            <div className="appearance-options" role="radiogroup" aria-label="Appearance">
              {themes.map((theme) => (
                <label className={appearance === theme.value ? 'selected' : ''} key={theme.value}>
                  <Icon name={theme.icon} size={23} />
                  <span>{theme.label}</span>
                  <input
                    type="radio"
                    name="appearance"
                    value={theme.value}
                    checked={appearance === theme.value}
                    onChange={() => setAppearance(theme.value)}
                  />
                </label>
              ))}
            </div>
            <p className="settings-help">
              Reduced motion, reduced transparency and increased contrast follow your browser’s
              accessibility preferences.
            </p>
          </section>
        </div>
        <div>
          <section className="settings-card panel">
            <Icon name="layers" size={26} />
            <h2>{mode === 'sample' ? 'Explore freely.' : 'Connected to your API.'}</h2>
            <p>
              {mode === 'sample'
                ? 'The sample workspace is a local, disposable preview. It never sends review actions to the backend.'
                : 'This workspace reads your configured API. Approved resolutions update its ledger, and are audited.'}
            </p>
            <div className="settings-facts">
              <div>
                <span>Data</span>
                <strong>Synthetic demonstration</strong>
              </div>
              <div>
                <span>Agent</span>
                <strong>
                  {mode === 'sample'
                    ? 'Illustrated sample'
                    : (snapshot.metrics?.provider ?? 'Unavailable')}
                </strong>
              </div>
              <div>
                <span>Currency</span>
                <strong>ZAR · integer cents</strong>
              </div>
            </div>
            {mode === 'sample' ? (
              <>
                <button className="secondary-button full" onClick={resetSample}>
                  <Icon name="refresh" size={16} />
                  Reset sample decisions
                </button>
                {!isDemoDeployment() && (
                  <Link className="text-link" to="/workspace/overview">
                    Open connected workspace <Icon name="arrow" size={15} />
                  </Link>
                )}
              </>
            ) : (
              <Link className="text-link" to="/sample/overview">
                Explore sample workspace <Icon name="arrow" size={15} />
              </Link>
            )}
          </section>
          <section className="settings-card safeguards">
            <Icon name="shield" size={26} />
            <h2>Human judgment stays.</h2>
            <p>
              Automatic agent matches must be full, single-invoice payments within the configured
              limit, with sufficient confidence, prior customer history and no conflicting proof or
              risk flags.
            </p>
            <p>
              Splits, shortfalls, excess funds and uncertain cases come to you. Current balances are
              rechecked before a connected review is applied.
            </p>
            <Link className="text-link" to={`${basePath}/review`}>
              Go to payment review <Icon name="arrow" size={15} />
            </Link>
          </section>
        </div>
      </div>
    </>
  );
}
