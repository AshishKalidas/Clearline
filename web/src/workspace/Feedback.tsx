import { useEffect, useRef, useState } from 'react';
import { Icon } from '../Icon';
import { usePreferences } from './Preferences';
import { useWorkspace } from './Workspace';

export function Toast({ message, clear }: { message: string | null; clear: () => void }) {
  const dismiss = useRef(clear);
  useEffect(() => {
    dismiss.current = clear;
  }, [clear]);
  useEffect(() => {
    if (!message) return;
    // Polling and parent renders must not extend a notification's lifetime.
    const timer = setTimeout(() => dismiss.current(), 5500);
    return () => clearTimeout(timer);
  }, [message]);
  if (!message) return null;
  return (
    <div className="toast" role="status">
      <Icon name="check" />
      <span>{message}</span>
      <button className="icon-button" aria-label="Dismiss notification" onClick={clear}>
        <Icon name="close" size={16} />
      </button>
    </div>
  );
}
export function ReconcileAction() {
  const { mode, request, reload } = useWorkspace();
  const { credentials } = usePreferences();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (mode === 'sample') return null;
  async function reconcile() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await request<{
        agent_cases: number;
        rules: { matched: number; reversed: number };
      }>('/runs/reconcile', { method: 'POST' }, credentials);
      setMessage(
        result.agent_cases || result.rules.matched || result.rules.reversed
          ? `${result.rules.matched} exact matches, ${result.rules.reversed} reversals, ${result.agent_cases} investigations.`
          : 'The feed is up to date. No new bank lines need investigation.',
      );
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Reconciliation failed.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="reconcile-action">
      <button className="primary-button" disabled={busy} onClick={() => void reconcile()}>
        <Icon name="bolt" size={17} />
        {busy ? 'Reconciling…' : 'Reconcile feed'}
      </button>
      {error && (
        <span className="form-error action-error" role="alert">
          {error}
        </span>
      )}
      <Toast message={message} clear={() => setMessage(null)} />
    </div>
  );
}
