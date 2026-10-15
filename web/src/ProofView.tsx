import { useRef, useState } from 'react';
import { Icon } from './Icon';
import { dateLabel, money } from './api';
import { useWorkspaceRequest } from './workspace/Workspace';
import type { BankLine, Credentials, PopResult } from './types';

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

export function ProofView({ credentials }: { credentials: Credentials }) {
  const request = useWorkspaceRequest();
  const [file, setFile] = useState<File | null>(null);
  const [invoice, setInvoice] = useState('');
  const [result, setResult] = useState<PopResult | null>(null);
  const [bank, setBank] = useState<BankLine | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  async function verify() {
    if (!file || busy) return;
    if (file.size > 5000000) {
      setError('Choose a PDF smaller than 5 MB.');
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    setBank(null);
    const data = new FormData();
    data.append('file', file);
    if (invoice.trim()) data.append('claimed_invoice_number', invoice.trim().toUpperCase());
    try {
      const verdict = await request<PopResult>(
        '/pops',
        { method: 'POST', body: data },
        credentials,
      );
      setResult(verdict);
      if (verdict.matched_bank_line_id) {
        const lines = await request<BankLine[]>('/bank-lines?limit=1000');
        setBank(lines.find((line) => line.id === verdict.matched_bank_line_id) ?? null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not verify this document.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="proof-workspace">
      <section className="proof-upload panel">
        <span className="eyebrow">BANK EVIDENCE FIRST</span>
        <h2>A claim isn’t a clearance.</h2>
        <p className="subtle">Check the payment against the bank feed before releasing goods.</p>
        <button
          className={`dropzone ${file ? 'has-file' : ''}`}
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
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setResult(null);
            setError(null);
          }}
        />
        <label>
          Claimed invoice <span className="subtle">Optional</span>
          <input
            value={invoice}
            placeholder="INV-100123"
            onChange={(e) => setInvoice(e.target.value)}
          />
        </label>
        <button
          className="primary-button full"
          disabled={!file || busy}
          onClick={() => void verify()}
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
              <span />
              <span />
              <span />
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
