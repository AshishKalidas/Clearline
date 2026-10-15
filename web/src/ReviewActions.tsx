import { useEffect, useRef, useState } from 'react';
import { Icon } from './Icon';
import { money } from './api';
import { useWorkspaceRequest } from './workspace/Workspace';
import type { Allocation, Decision, Invoice, ProposalDetail, Resolution } from './types';

export interface ReviewActionsProps {
  detail: ProposalDetail;
  busy: boolean;
  onDecision: (
    action: 'approve' | 'reject',
    note: string,
    correction?: Resolution,
  ) => Promise<void>;
}

/** Every human action carries an identity; rejection and correction require context. */
export function ReviewActions({ detail, busy, onDecision }: ReviewActionsProps) {
  const request = useWorkspaceRequest();
  const [mode, setMode] = useState<'approve' | 'reject' | 'correct'>('approve');
  const [note, setNote] = useState('');
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [allocations, setAllocations] = useState<Allocation[]>(detail.allocations);
  const [decision, setDecision] = useState<Decision>(detail.decision);
  const [error, setError] = useState<string | null>(null);
  const noteInput = useRef<HTMLTextAreaElement>(null);
  const mismatch = detail.linked_pops?.some((p) => p.verdict === 'mismatch');
  const noteRequired = mode !== 'approve' || mismatch;

  useEffect(() => {
    setMode('approve');
    setNote('');
    setError(null);
    setAllocations(detail.allocations);
    setDecision(detail.decision);
  }, [detail.id]);
  useEffect(() => {
    if (mode !== 'approve') noteInput.current?.focus();
  }, [mode]);
  useEffect(() => {
    if (mode !== 'correct') return;
    const controller = new AbortController();
    request<Invoice[]>('/invoices', { signal: controller.signal })
      .then(setInvoices)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [mode]);

  async function submit(action: 'approve' | 'reject') {
    if (busy) return;
    if (noteRequired && !note.trim()) {
      setError('Add a review note before continuing.');
      return;
    }
    const correction: Resolution | undefined =
      mode === 'correct'
        ? {
            decision,
            allocations: decision === 'escalate' || decision === 'duplicate' ? [] : allocations,
            confidence: 1,
            reasoning: note.trim(),
            evidence: [],
            risk_flags: [],
          }
        : undefined;
    if (
      correction &&
      !['duplicate', 'escalate'].includes(decision) &&
      (!allocations.length ||
        allocations.some(
          (a) => !a.invoice_number || !Number.isSafeInteger(a.amount_cents) || a.amount_cents <= 0,
        ))
    ) {
      setError('Choose invoices and enter positive amounts in integer cents.');
      return;
    }
    setError(null);
    await onDecision(action, note.trim(), correction);
  }

  useEffect(() => {
    function keydown(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (
        busy ||
        target.closest('input, textarea, select, [contenteditable="true"]') ||
        event.ctrlKey ||
        event.metaKey ||
        event.altKey ||
        event.repeat
      )
        return;
      if (event.key.toLowerCase() === 'a' && mode === 'approve') {
        event.preventDefault();
        void submit('approve');
      }
      if (event.key.toLowerCase() === 'r') {
        event.preventDefault();
        setMode('reject');
      }
      if (event.key === 'Escape') {
        setMode('approve');
        setError(null);
      }
    }
    window.addEventListener('keydown', keydown);
    return () => window.removeEventListener('keydown', keydown);
  });

  return (
    <aside className="review-panel">
      <div className="section-heading">
        <h3>Your decision</h3>
        <Icon name="shield" />
      </div>
      <p className="review-intro">The agent proposes. You make the call.</p>
      <div className="policy-notice">
        <Icon name="info" />
        <div>
          <strong>Human sign-off required</strong>
          <p>{detail.policy_reason}</p>
        </div>
      </div>
      {mode === 'correct' && (
        <div className="correction-form">
          <label>
            Corrected decision
            <select value={decision} onChange={(e) => setDecision(e.target.value as Decision)}>
              {['match', 'partial', 'split', 'overpayment', 'duplicate', 'escalate'].map((d) => (
                <option key={d} value={d}>
                  {d.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </label>
          {!['escalate', 'duplicate'].includes(decision) && (
            <>
              {allocations.map((allocation, index) => (
                <div className="allocation-edit" key={index}>
                  <label>
                    Invoice {index + 1}
                    <select
                      aria-label={`Corrected invoice ${index + 1}`}
                      value={allocation.invoice_number}
                      onChange={(e) =>
                        setAllocations((a) =>
                          a.map((row, n) =>
                            n === index ? { ...row, invoice_number: e.target.value } : row,
                          ),
                        )
                      }
                    >
                      <option value="">Choose an open invoice</option>
                      {invoices.map((i) => (
                        <option value={i.invoice_number} key={i.id}>
                          {i.invoice_number} · {i.customer_name} · {money(i.outstanding_cents)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="cents-row">
                    <label>
                      Amount (integer cents)
                      <input
                        inputMode="numeric"
                        type="number"
                        min="1"
                        step="1"
                        aria-label={`Corrected amount ${index + 1}`}
                        value={allocation.amount_cents || ''}
                        onChange={(e) =>
                          setAllocations((a) =>
                            a.map((row, n) =>
                              n === index ? { ...row, amount_cents: Number(e.target.value) } : row,
                            ),
                          )
                        }
                      />
                    </label>
                    <button
                      className="icon-button"
                      aria-label={`Remove allocation ${index + 1}`}
                      onClick={() => setAllocations((a) => a.filter((_, n) => n !== index))}
                    >
                      <Icon name="close" />
                    </button>
                  </div>
                </div>
              ))}
              <button
                className="text-button"
                onClick={() =>
                  setAllocations((a) => [...a, { invoice_number: '', amount_cents: 0 }])
                }
              >
                + Add invoice allocation
              </button>
            </>
          )}
        </div>
      )}
      <label className="note-label">
        {mode === 'correct' ? 'Correction rationale' : 'Review note'}{' '}
        <span className="subtle">{noteRequired ? 'Required' : 'Optional'}</span>
        <textarea
          ref={noteInput}
          aria-label="Review note"
          value={note}
          maxLength={3000}
          onChange={(e) => setNote(e.target.value)}
          placeholder={
            mode === 'reject'
              ? 'Why does this need further investigation?'
              : 'Add context to the audit trail…'
          }
          rows={mode === 'approve' ? 3 : 4}
        />
      </label>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {mode === 'approve' ? (
        <>
          <button
            className="primary-button full"
            disabled={busy}
            onClick={() => void submit('approve')}
          >
            <Icon name="check" />
            Approve proposal<kbd>A</kbd>
          </button>
          <div className="action-pair">
            <button className="secondary-button" disabled={busy} onClick={() => setMode('reject')}>
              Reject <kbd>R</kbd>
            </button>
            <button className="secondary-button" disabled={busy} onClick={() => setMode('correct')}>
              <Icon name="edit" size={15} />
              Correct
            </button>
          </div>
        </>
      ) : (
        <>
          <button
            className={mode === 'reject' ? 'danger-button full' : 'primary-button full'}
            disabled={busy || !note.trim()}
            onClick={() => void submit('reject')}
          >
            {busy
              ? 'Saving decision…'
              : mode === 'reject'
                ? 'Reject proposal'
                : 'Save corrected resolution'}
          </button>
          <button className="text-button full" disabled={busy} onClick={() => setMode('approve')}>
            Cancel
          </button>
        </>
      )}
      <div className="signoff-footnote">
        <Icon name="shield" size={15} />
        <span>Balances are rechecked before applying. Every decision is audited.</span>
      </div>
    </aside>
  );
}
