import { Link, useSearchParams } from 'react-router-dom';
import { Icon } from '../Icon';
import {
  findRun,
  gateLabels,
  measuredDate,
  metricDefinitions,
  metricValue,
  providers,
  type Provider,
} from '../evaluation/evidence';
import { PageHeader } from '../workspace/PageHeader';

/** Published evidence is a build-time snapshot, never a metric synthesized from sample activity. */
export function EvaluationPage() {
  const [params, setParams] = useSearchParams();
  const provider: Provider =
    params.get('provider') === 'claude'
      ? 'claude'
      : params.get('provider') === 'mimo'
        ? 'mimo'
        : 'stub';
  const retrieval = params.get('retrieval') !== 'off';
  const selected = findRun(provider, retrieval);
  const report = selected.report;
  function choose(key: string, value: string) {
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      next.set(key, value);
      return next;
    });
  }
  return (
    <>
      <PageHeader
        eyebrow="Measured. Traceable. Explicit."
        title="Evidence, in the open."
        description="Published synthetic evaluations, with the denominators and limits that make the results meaningful."
      />
      <section className="evidence-intro panel">
        <div className="evidence-intro-icon">
          <Icon name="shield" size={28} />
        </div>
        <div>
          <h2>A baseline is a starting point.</h2>
          <p>
            The stub follows a script. Its results exercise orchestration, policy, proofs and ledger
            controls. They do not establish live-model reasoning or real-world fraud detection.
          </p>
          <p>
            These are reports packaged with this build, independent of your current workspace and
            API connection. Live runs remain “Not yet run” until measured.
          </p>
        </div>
      </section>
      <section className="evaluation-card panel" aria-labelledby="comparison-heading">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Same questions. Visible evidence.</span>
            <h2 id="comparison-heading">Compare the measured runs.</h2>
          </div>
          <nav className="evaluation-switch" aria-label="Retrieval configuration">
            {(['on', 'off'] as const).map((value) => {
              const query = new URLSearchParams(params);
              query.set('retrieval', value);
              const active = retrieval === (value === 'on');
              return (
                <Link
                  key={value}
                  to={`?${query}`}
                  className={active ? 'selected' : ''}
                  aria-current={active ? 'true' : undefined}
                >
                  Retrieval {value}
                </Link>
              );
            })}
          </nav>
        </div>
        <p className="table-scroll-hint" id="comparison-scroll-help">
          Scroll sideways to compare all providers. <Icon name="arrow" size={14} />
        </p>
        <div
          className="evaluation-table-scroll"
          aria-describedby="comparison-scroll-help"
          role="region"
          aria-label="Evaluation comparison"
          tabIndex={0}
        >
          <table className="evaluation-table">
            <caption>
              Published results · retrieval {retrieval ? 'on' : 'off'} · all data synthetic
            </caption>
            <thead>
              <tr>
                <th scope="col">Measurement</th>
                {providers.map((item) => (
                  <th scope="col" key={item.id}>
                    {item.name}
                    <small>{findRun(item.id, retrieval).report?.model ?? 'No published run'}</small>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metricDefinitions.map((metric) => (
                <tr key={metric.key}>
                  <th scope="row">
                    {metric.label}
                    <small>{metric.note}</small>
                  </th>
                  {providers.map((item) => (
                    <td key={item.id}>
                      {metricValue(findRun(item.id, retrieval).report, metric.key, metric.format)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <div className="report-heading">
        <h2>Inside a report.</h2>
        <label>
          Inspect provider
          <select value={provider} onChange={(event) => choose('provider', event.target.value)}>
            {providers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {report ? (
        <>
          <div className="evaluation-population" aria-label="Evaluation denominators">
            {[
              ['Bank cases', report.counts.bank_cases],
              ['Agent investigations', report.counts.agent_cases],
              ['Agent auto allocations', report.counts.auto_applied],
              ['Wrong auto allocations', report.counts.wrong_auto_applied],
              ['Proof documents', report.counts.pop_cases],
            ].map(([label, value]) => (
              <div className="panel" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          <div className="evaluation-detail-grid">
            <section className="evaluation-card panel" aria-labelledby="release-gates-heading">
              <div className="section-heading">
                <h2 id="release-gates-heading">The release boundary.</h2>
                <span className={`status-badge ${report.passed ? 'success' : 'unsafe'}`}>
                  {report.passed ? 'Gates passed' : 'Gates failed'}
                </span>
              </div>
              <p className="subtle">
                Recorded gate outcomes are independently checked when this snapshot is generated.
              </p>
              <ul className="gate-list">
                {Object.entries(report.gates).map(([key, passed]) => (
                  <li key={key}>
                    <Icon name={passed ? 'check' : 'close'} size={18} />
                    <span>{gateLabels[key] ?? key.replaceAll('_', ' ')}</span>
                    <strong className={passed ? '' : 'form-error'}>
                      {passed ? 'Passed' : 'Failed'}
                    </strong>
                  </li>
                ))}
              </ul>
              <p className="settings-help">
                {report.failure_count} labelled failures · {report.invariant_errors.length}{' '}
                invariant errors. Passing applies to this evaluated fixture set.
              </p>
            </section>
            <section className="evaluation-card panel" aria-labelledby="scenario-heading">
              <h2 id="scenario-heading">Every scenario has a denominator.</h2>
              <p className="subtle">
                Agent decision and invoice-set agreement. Exact-rule cases are counted separately.
              </p>
              <div className="scenario-scores">
                {Object.entries(report.scenarios).map(([scenario, score]) => (
                  <div key={scenario}>
                    <span>{scenario.replaceAll('_', ' ')}</span>
                    <meter
                      min={0}
                      max={score.total}
                      value={score.correct}
                      aria-label={`${scenario.replaceAll('_', ' ')} accuracy`}
                    />
                    <strong>
                      {score.correct} / {score.total}
                    </strong>
                  </div>
                ))}
              </div>
            </section>
          </div>
          <section
            className="evaluation-card panel provenance"
            aria-labelledby="provenance-heading"
          >
            <div className="section-heading">
              <h2 id="provenance-heading">A result you can trace.</h2>
              <a
                className="secondary-button"
                href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(selected, null, 2))}`}
                download={`clearline-${provider}-retrieval-${retrieval ? 'on' : 'off'}-snapshot.json`}
              >
                Download snapshot <Icon name="arrow" size={15} />
              </a>
            </div>
            <dl>
              <div>
                <dt>Measured</dt>
                <dd>{measuredDate(report.created_at)} · Africa/Johannesburg</dd>
              </div>
              <div>
                <dt>Database</dt>
                <dd>{report.database}</dd>
              </div>
              <div>
                <dt>Embedding method</dt>
                <dd>
                  {report.embedder === 'hash'
                    ? 'Hash features · nonsemantic baseline'
                    : 'Local semantic model'}
                </dd>
              </div>
              <div>
                <dt>Dataset seed</dt>
                <dd>{report.seed}</dd>
              </div>
              <div>
                <dt>Source report</dt>
                <dd>
                  evals/reports/{provider}-{retrieval ? 'on' : 'off'}/report.json
                </dd>
              </div>
              <div>
                <dt>Source file SHA-256</dt>
                <dd className="mono">{selected.report_sha256}</dd>
              </div>
              <div>
                <dt>Dataset SHA-256</dt>
                <dd className="mono">{report.dataset_sha256}</dd>
              </div>
            </dl>
            <p className="settings-help">
              The fingerprint identifies the original report file in the source tree. The download
              contains its validated projection and that fingerprint. Hash retrieval lift does not
              measure semantic retrieval quality; live cost stays unpriced until measured and priced
              explicitly.
            </p>
          </section>
        </>
      ) : (
        <section className="evaluation-card panel unmeasured-report">
          <Icon name="clock" size={34} />
          <h2>Not yet run.</h2>
          <p>
            No {providers.find((item) => item.id === provider)?.name} report is published for
            retrieval {retrieval ? 'on' : 'off'}. No score, token count, latency or release outcome
            is inferred from the stub.
          </p>
          <p>
            Provider integrations are tested against recorded SDK responses. A live evaluation still
            requires an explicitly configured model and credentials.
          </p>
        </section>
      )}
    </>
  );
}
