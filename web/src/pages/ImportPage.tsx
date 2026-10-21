import { useRef } from 'react';
import { Link } from 'react-router-dom';
import { money } from '../api';
import { isDemoDeployment } from '../deployment';
import { Icon } from '../Icon';
import { columnLabels, templates } from '../imports/templates';
import { useCsvImport } from '../imports/useCsvImport';
import { usePreferences } from '../workspace/Preferences';
import { useWorkspace } from '../workspace/Workspace';
import { PageHeader } from '../workspace/PageHeader';
import { ReconcileAction } from '../workspace/Feedback';

/** Preview validates the entire file; only an explicit import sends a persistent write. */
export function ImportPage() {
  const { mode, basePath, request, reload } = useWorkspace();
  const { credentials } = usePreferences();
  const { state, busy, selectKind, selectFile, confirm, validate, importFile } = useCsvImport({
    enabled: mode === 'connected',
    request,
    credentials,
    onImported: reload,
  });
  const { kind, file, phase } = state;
  const preview = 'preview' in state ? state.preview : null;
  const result = state.phase === 'done' ? state.result : null;
  const problem = 'problem' in state ? state.problem : null;
  const confirmed = state.phase === 'ready' && state.confirmed;
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <PageHeader
        eyebrow="Start with good evidence"
        title="Bring your records together."
        description={
          isDemoDeployment()
            ? 'Explore the invoice and bank-feed formats with fictional CSV templates.'
            : 'Check a CSV, inspect its contents, then import it into the connected workspace.'
        }
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
                    selectKind(value);
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
              {isDemoDeployment() ? (
                <a
                  className="primary-button"
                  href="https://github.com/AshishKalidas/Clearline#run-the-complete-demo"
                >
                  Run the complete workspace <Icon name="arrow" size={16} />
                </a>
              ) : (
                <Link className="primary-button" to="/workspace/import">
                  Open connected imports <Icon name="arrow" size={16} />
                </Link>
              )}
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
                  onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
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
              {problem && (
                <div className="import-errors" role="alert">
                  <strong>{problem.message}</strong>
                  {problem.issues.length > 0 && (
                    <>
                      <p>
                        {problem.issueCount} {problem.issueCount === 1 ? 'issue' : 'issues'} found
                        {problem.issueCount > problem.issues.length
                          ? `; showing the first ${problem.issues.length}`
                          : ''}
                        .
                      </p>
                      <ul>
                        {problem.issues.map((issue, index) => (
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
                      onChange={(event) => confirm(event.target.checked)}
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
