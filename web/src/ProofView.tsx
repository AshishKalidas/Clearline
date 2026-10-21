import { useRef, useState } from 'react';
import { Icon } from './Icon';
import { dateLabel, money } from './api';
import { useProofVerification } from './proofs/useProofVerification';
import { useWorkspaceRequest } from './workspace/Workspace';
import type { Credentials } from './types';

const checkNames: Record<string, string> = {
  bank_presence: 'Payment in bank feed',
  amount: 'Amount agrees',
  date_within_two_days: 'Value date within two days',
  payer: 'Payer agrees',
  reference: 'Payment reference agrees',
  beneficiary: 'Beneficiary account agrees',
  claimed_invoice: 'Claimed invoice agrees',
  required_fields: 'Required fields readable',
};

export function ProofView({
  credentials,
  onVerified,
}: {
  credentials: Credentials;
  onVerified: () => void;
}) {
  const request = useWorkspaceRequest();
  const [file, setFile] = useState<File | null>(null);
  const [invoice, setInvoice] = useState('');
  const { state, busy, reset, verify } = useProofVerification({ request, credentials, onVerified });
  const result = 'result' in state ? state.result : null;
  const bank = state.phase === 'complete' ? state.bank : null;
  const error = state.phase === 'idle' ? state.error : null;
  const fileInput = useRef<HTMLInputElement>(null);

  return (
    <div className="proof-workspace">
      <section className="proof-upload panel">
        <span className="eyebrow">BANK EVIDENCE FIRST</span>
        <h2>A claim isn’t a clearance.</h2>
        <p className="subtle">Check the payment against the bank feed before releasing goods.</p>
        <button
          className={`dropzone ${file ? 'has-file' : ''}`}
          disabled={busy}
          onClick={() => fileInput.current?.click()}
        >
          <div className="upload-symbol">
            <Icon name={file ? 'proof' : 'upload'} size={30} />
          </div>
          <strong>{file?.name ?? 'Choose a proof of payment'}</strong>
          <span>
            {file
              ? `${Math.ceil(file.size / 1024)} KB · Click to change`
              : 'Text-based PDF · Up to 5 MB'}
          </span>
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="application/pdf,.pdf"
          aria-label="Proof of payment PDF"
          className="visually-hidden"
          disabled={busy}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            reset();
          }}
        />
        <label>
          Claimed invoice <span className="subtle">Optional</span>
          <input
            value={invoice}
            disabled={busy}
            placeholder="INV-100123"
            onChange={(e) => {
              setInvoice(e.target.value);
              reset();
            }}
          />
        </label>
        <button
          className="primary-button full"
          disabled={!file || busy}
          onClick={() => void verify(file, invoice)}
        >
          <Icon name="shield" />
          {busy ? 'Checking bank evidence…' : 'Verify payment claim'}
          <Icon name="arrow" />
        </button>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <p className="proof-note">
          <Icon name="info" size={16} />
          Synthetic demonstration. A verified claim still requires checking invoice settlement and
          dispatch authorization.
        </p>
      </section>
      <section className="proof-result panel" aria-live="polite">
        {result ? (
          <>
            <div
              className={`verdict-heading ${result.verdict === 'verified' ? 'verified' : 'unsafe'}`}
            >
              <div className="verdict-icon">
                <Icon name={result.verdict === 'verified' ? 'check' : 'shield'} size={27} />
              </div>
              <span className="eyebrow">VERIFICATION RESULT</span>
              <h2>{result.verdict.replaceAll('_', ' ')}</h2>
              <p>{result.summary}</p>
            </div>
            <div className="proof-checks">
              <h3>Independent checks</h3>
              {result.checks.map((c) => (
                <div className="proof-check" key={c.check}>
                  <span className={c.passed ? 'check-pass' : 'check-fail'}>
                    <Icon name={c.passed ? 'check' : 'close'} size={17} />
                  </span>
                  <div>
                    <strong>{checkNames[c.check] ?? c.check}</strong>
                    {c.claimed !== undefined && (
                      <small>
                        Claim: {c.check === 'amount' ? money(Number(c.claimed)) : c.claimed} · Bank:{' '}
                        {c.check === 'amount' ? money(Number(c.observed)) : c.observed}
                      </small>
                    )}
                  </div>
                  <span className="subtle">{c.passed ? 'Agrees' : 'Failed'}</span>
                </div>
              ))}
            </div>
            {state.phase === 'loading-bank' && <p role="status">Loading linked bank evidence…</p>}
            {state.phase === 'complete' && state.evidenceError && (
              <p className="form-error" role="alert">
                {state.evidenceError}
              </p>
            )}
            {bank && (
              <div className="bank-proof">
                <span className="eyebrow">LINKED BANK OBSERVATION</span>
                <strong>{money(bank.amount_cents)}</strong>
                <p>{bank.payer_name}</p>
                <span className="mono">{bank.raw_reference}</span>
                <small>
                  {dateLabel(bank.value_date)} · {bank.status.replaceAll('_', ' ')}
                </small>
              </div>
            )}
          </>
        ) : (
          <div className="proof-placeholder">
            <div className="evidence-illustration">
              <Icon name="shield" size={43} />
            </div>
            <h3>Trust the bank feed.</h3>
            <p>
              Your document’s amount, date, payer, reference and beneficiary will be checked against
              bank evidence.
            </p>
            <div className="verdict-examples">
              <span>Verified</span>
              <span>Not received</span>
              <span>Mismatch</span>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
