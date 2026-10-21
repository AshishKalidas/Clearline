import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, money, type CsvIssue } from '../api';
import { Icon } from '../Icon';
import {
  columnLabels,
  templates,
  type ImportKind,
  type ImportPreview,
  type ImportResult,
} from '../imports/templates';
import { usePreferences } from '../workspace/Preferences';
import { useWorkspace } from '../workspace/Workspace';
import { PageHeader } from '../workspace/PageHeader';
import { ReconcileAction } from '../workspace/Feedback';

type Phase = 'idle' | 'validating' | 'ready' | 'importing' | 'done';

/** Preview validates the entire file; only an explicit import sends a persistent write. */
export function ImportPage() {
  const { mode, basePath, request, reload } = useWorkspace();
  const { credentials } = usePreferences();
  const [kind, setKind] = useState<ImportKind>('invoices');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [issues, setIssues] = useState<CsvIssue[]>([]);
  const [issueCount, setIssueCount] = useState(0);
  const [confirmed, setConfirmed] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const pending = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const busy = phase === 'validating' || phase === 'importing';
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      pending.current?.abort();
    };
  }, []);

  function reset(nextFile: File | null = null) {
    setFile(nextFile);
    setPreview(null);
    setResult(null);
    setError(null);
    setIssues([]);
    setIssueCount(0);
    setConfirmed(false);
    setPhase('idle');
  }
  function showError(cause: unknown) {
    setError(
      cause instanceof Error ? cause.message : 'The import could not be completed. Please retry.',
    );
    setIssues(cause instanceof ApiError ? cause.issues : []);
    setIssueCount(cause instanceof ApiError ? cause.issueCount : 0);
  }
  async function validate() {
    if (!file || busy || mode !== 'connected') return;
    if (file.size > 5_000_000) {
      setError('Choose a CSV no larger than 5 MB.');
      return;
    }
    const controller = new AbortController();
    pending.current = controller;
    setPhase('validating');
    setError(null);
    setIssues([]);
    setIssueCount(0);
    setPreview(null);
    setConfirmed(false);
    const deadline = setTimeout(() => controller.abort(), 15000);
    const body = new FormData();
    body.append('file', file);
    try {
      const checked = await request<ImportPreview>(
        `/ingest/${kind}/preview`,
        { method: 'POST', body, signal: controller.signal },
        credentials,
      );
      if (mounted.current) {
        setPreview(checked);
        setPhase('ready');
      }
    } catch (cause) {
      if (mounted.current) {
        if (controller.signal.aborted)
          setError('Validation took too long. Try a smaller file or retry.');
        else showError(cause);
        setPhase('idle');
      }
    } finally {
      clearTimeout(deadline);
      pending.current = null;
    }
  }
  async function importFile() {
    if (!file || !preview || !confirmed || busy || phase === 'done' || mode !== 'connected') return;
    setPhase('importing');
    setError(null);
    setIssues([]);
    setIssueCount(0);
    const body = new FormData();
    body.append('file', file);
    try {
      const imported = await request<ImportResult>(
        `/ingest/${kind}`,
        { method: 'POST', body },
        credentials,
      );
      reload();
      if (mounted.current) {
        setResult(imported);
        setPhase('done');
      }
    } catch (cause) {
      if (mounted.current) {
        showError(cause);
        setPhase('ready');
      }
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="Start with good evidence"
        title="Bring your records together."
        description="Check a CSV, inspect its contents, then import it into the connected workspace."
      />
      <div className="import-layout">
        <section className="import-card panel" aria-labelledby="import-heading">
          <div className="section-heading">
            <h2 id="import-heading">A careful first step.</h2>
            <Icon name="upload" size={22} />
          </div>
          <p className="subtle">
            Import invoices first, then bank observations. Use the templates to try the workflow
            with fictional data.
          </p>
          <fieldset className="import-kind" disabled={busy}>
            <legend>What are you importing?</legend>
            {(['invoices', 'bank-lines'] as const).map((value) => (
              <label key={value} className={kind === value ? 'selected' : ''}>
                <input
                  type="radio"
                  name="import-kind"
                  checked={kind === value}
                  onChange={() => {
                    setKind(value);
                    reset();
                    if (input.current) input.current.value = '';
                  }}
                />
                <Icon name={value === 'invoices' ? 'proof' : 'activity'} size={20} />
                {templates[value].label}
              </label>
            ))}
          </fieldset>
          <a
            className="text-link template-link"
            href={`data:text/csv;charset=utf-8,${encodeURIComponent(templates[kind].csv)}`}
            download={`clearline-${kind}-template.csv`}
          >
            Download {kind === 'invoices' ? 'invoice' : 'bank observation'} template{' '}
            <Icon name="arrow" size={15} />
          </a>
          {mode === 'sample' ? (
            <div className="import-sample-notice">
              <Icon name="layers" size={24} />
              <h3>Keep the sample a safe place.</h3>
              <p>
                Templates are available here. CSV validation and imports use your connected API;
                sample records stay unchanged.
              </p>
              <Link className="primary-button" to="/workspace/import">
                Open connected imports <Icon name="arrow" size={16} />
              </Link>
            </div>
          ) : (
            <>
              <label className="csv-file-label">
                CSV file
                <input
                  ref={input}
                  type="file"
                  accept=".csv,text/csv"
                  disabled={busy}
                  onChange={(event) => reset(event.target.files?.[0] ?? null)}
                  aria-describedby="csv-file-help"
                />
              </label>
              <p id="csv-file-help" className="settings-help">
                UTF-8 CSV · Up to 5 MB and 10 000 records · Amounts in integer cents. Bank account
                suffixes contain four digits.
              </p>
              <button
                className="secondary-button full"
                disabled={!file || busy || phase === 'done'}
                onClick={() => void validate()}
              >
                <Icon name="search" size={17} />
                {phase === 'validating' ? 'Checking every record…' : 'Validate and preview'}
              </button>
              {error && (
                <div className="import-errors" role="alert">
                  <strong>{error}</strong>
                  {issues.length > 0 && (
                    <>
                      <p>
                        {issueCount} {issueCount === 1 ? 'issue' : 'issues'} found
                        {issueCount > issues.length ? `; showing the first ${issues.length}` : ''}.
                      </p>
                      <ul>
                        {issues.map((issue, index) => (
                          <li key={index}>
                            Row {issue.row}
                            {issue.field
                              ? ` · ${columnLabels[issue.field] ?? issue.field}`
                              : ''}: {issue.message}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </section>
        <section
          className="import-card panel"
          aria-labelledby="csv-preview-heading"
          aria-busy={busy}
        >
          <div className="section-heading">
            <h2 id="csv-preview-heading">See it before you save it.</h2>
            <Icon name="shield" size={22} />
          </div>
          {preview ? (
            <>
              <div className="preview-summary">
                <span className="status-badge success">
                  <Icon name="check" size={15} />
                  Format validated
                </span>
                <strong>
                  {preview.row_count.toLocaleString('en-ZA')}{' '}
                  {preview.row_count === 1 ? 'record' : 'records'}
                </strong>
              </div>
              <p className="subtle">
                Showing the first {preview.rows.length}. Every record was checked. Existing-data
                conflicts are checked when you import.
              </p>
              <div
                className="csv-preview-scroll"
                role="region"
                aria-label="CSV preview records"
                tabIndex={0}
              >
                <table>
                  <thead>
                    <tr>
                      {preview.columns.map((column) => (
                        <th key={column}>{columnLabels[column] ?? column}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row, index) => (
                      <tr key={index}>
                        {preview.columns.map((column) => (
                          <td key={column}>
                            {column === 'amount_cents'
                              ? money(Number(row[column]))
                              : String(row[column] ?? '—')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {result ? (
                <div className="import-complete" role="status">
                  <Icon name="check" size={25} />
                  <h3>Records, together.</h3>
                  <p>
                    {result.inserted} imported · {result.skipped} already present and skipped.
                  </p>
                  <p>
                    No invoices were settled by this import. Reconcile the feed when both files are
                    ready.
                  </p>
                  <div className="import-next-actions">
                    <ReconcileAction />
                    <Link className="text-link" to={`${basePath}/overview`}>
                      Go to overview <Icon name="arrow" size={15} />
                    </Link>
                  </div>
                </div>
              ) : (
                <div className="import-confirmation">
                  <label>
                    <input
                      type="checkbox"
                      checked={confirmed}
                      disabled={busy}
                      onChange={(event) => setConfirmed(event.target.checked)}
                    />
                    <span>
                      Import {preview.row_count} validated{' '}
                      {preview.row_count === 1 ? 'record' : 'records'} into the connected workspace.
                    </span>
                  </label>
                  <button
                    className="primary-button"
                    disabled={!confirmed || busy}
                    onClick={() => void importFile()}
                  >
                    <Icon name="upload" size={17} />
                    {phase === 'importing' ? 'Importing…' : 'Import records'}
                  </button>
                  <p className="settings-help">
                    The entire file succeeds or rolls back. Re-importing identical records skips
                    them; existing records are never overwritten.
                  </p>
                </div>
              )}
            </>
          ) : (
            <div className="import-empty">
              <Icon name="proof" size={42} />
              <h3>Clarity starts with a preview.</h3>
              <p>
                Choose a file and validate it to see its record count, sample rows and any fields
                that need attention. Validation does not save records or call an AI model.
              </p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
