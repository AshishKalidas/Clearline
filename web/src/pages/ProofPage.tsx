import { useState } from 'react';
import { ProofView } from '../ProofView';
import { Icon } from '../Icon';
import { money } from '../api';
import { isDemoDeployment } from '../deployment';
import { usePreferences } from '../workspace/Preferences';
import { PageHeader } from '../workspace/PageHeader';
import { useWorkspace } from '../workspace/Workspace';
import { sampleProof, type ProofScenario } from '../workspace/sample';

const scenarios: {
  value: ProofScenario;
  title: string;
  description: string;
  icon: 'check' | 'clock' | 'info';
}[] = [
  {
    value: 'verified',
    title: 'A payment that arrived',
    description: 'A matching bank observation supports the claim.',
    icon: 'check',
  },
  {
    value: 'not_received',
    title: 'A convincing document. No funds.',
    description: 'The claim has no matching payment in the feed.',
    icon: 'clock',
  },
  {
    value: 'mismatch',
    title: 'An amount that doesn’t add up',
    description: 'The document and the bank disagree.',
    icon: 'info',
  },
];
function SampleProofView() {
  const [scenario, setScenario] = useState<ProofScenario>('verified');
  const [result, setResult] = useState<ReturnType<typeof sampleProof> | null>(null);
  return (
    <div className="proof-workspace">
      <section className="proof-upload panel">
        <span className="eyebrow">Try a sample claim</span>
        <h2>A claim isn’t a clearance.</h2>
        <p className="subtle">
          Explore three outcomes before checking your own imported bank feed.
        </p>
        <div className="proof-scenarios" role="radiogroup" aria-label="Sample proof scenario">
          {scenarios.map((item) => (
            <label
              className={`scenario-option ${scenario === item.value ? 'selected' : ''}`}
              key={item.value}
            >
              <input
                type="radio"
                name="proof-scenario"
                checked={scenario === item.value}
                onChange={() => {
                  setScenario(item.value);
                  setResult(null);
                }}
              />
              <Icon name={item.icon} size={20} />
              <span>
                <strong>{item.title}</strong>
                <small>{item.description}</small>
              </span>
            </label>
          ))}
        </div>
        <button className="primary-button full" onClick={() => setResult(sampleProof(scenario))}>
          Check sample claim <Icon name="arrow" size={17} />
        </button>
        <p className="proof-note">
          <Icon name="info" size={16} />
          Simulated verification. No PDF is uploaded or inspected.
          {!isDemoDeployment() && ' Switch to Connected for actual bank-feed checks.'}
        </p>
      </section>
      <section className="proof-result panel" aria-live="polite">
        {result ? (
          <>
            <div
              className={`verdict-heading ${result.verdict === 'verified' ? 'verified' : 'unsafe'}`}
            >
              <Icon name={result.verdict === 'verified' ? 'check' : 'shield'} size={30} />
              <span className="eyebrow">Illustrative verification</span>
              <h2>{result.verdict.replaceAll('_', ' ')}</h2>
              <p>{result.summary}</p>
            </div>
            <div className="proof-checks">
              <h3>Independent checks</h3>
              {result.checks.map((check) => (
                <div className="proof-check" key={check.check}>
                  <span className={check.passed ? 'check-pass' : 'check-fail'}>
                    <Icon name={check.passed ? 'check' : 'close'} size={18} />
                  </span>
                  <div>
                    <strong>{check.check.replaceAll('_', ' ')}</strong>
                    {check.check === 'amount' && (
                      <small>
                        Claim: {money(Number(check.claimed))} · Bank:{' '}
                        {money(Number(check.observed))}
                      </small>
                    )}
                  </div>
                  <span>{check.passed ? 'Agrees' : 'Failed'}</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="proof-placeholder">
            <div className="evidence-illustration">
              <Icon name="shield" size={42} />
            </div>
            <h2>Trust the bank feed.</h2>
            <p>Pick a scenario to see how independent evidence changes the outcome.</p>
          </div>
        )}
      </section>
    </div>
  );
}
export function ProofPage() {
  const { mode, reload } = useWorkspace();
  const { credentials } = usePreferences();
  return (
    <>
      <PageHeader
        eyebrow="Payment proofs"
        title="Verify before you release."
        description="A proof is a claim. The bank feed is the evidence."
      />
      {mode === 'sample' ? (
        <SampleProofView />
      ) : (
        <ProofView credentials={credentials} onVerified={reload} />
      )}
    </>
  );
}
