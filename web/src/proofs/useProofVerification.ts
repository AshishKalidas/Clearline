import { useEffect, useRef, useState } from 'react';
import type { WorkspaceRequest } from '../api';
import type { BankLine, Credentials, PopResult } from '../types';

type VerificationState =
  | { phase: 'idle'; error: string | null }
  | { phase: 'verifying' }
  | { phase: 'loading-bank'; result: PopResult }
  | { phase: 'complete'; result: PopResult; bank: BankLine | null; evidenceError: string | null };

interface VerificationOptions {
  request: WorkspaceRequest;
  credentials: Credentials;
  onVerified: () => void;
}

/** Keep a saved verdict even if its supplementary bank observation cannot be loaded. */
export function useProofVerification({ request, credentials, onVerified }: VerificationOptions) {
  const [state, setState] = useState<VerificationState>({ phase: 'idle', error: null });
  const mounted = useRef(true);
  const inFlight = useRef(false);
  const bankRead = useRef<AbortController | null>(null);
  const busy = state.phase === 'verifying' || state.phase === 'loading-bank';

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      bankRead.current?.abort();
    };
  }, []);

  function reset() {
    if (!inFlight.current) setState({ phase: 'idle', error: null });
  }

  async function verify(file: File | null, invoice: string) {
    if (!file || !mounted.current || inFlight.current) return;
    if (file.size > 5_000_000) {
      setState({ phase: 'idle', error: 'Choose a PDF no larger than 5 MB.' });
      return;
    }
    inFlight.current = true;
    setState({ phase: 'verifying' });
    const body = new FormData();
    body.append('file', file);
    if (invoice.trim()) body.append('claimed_invoice_number', invoice.trim().toUpperCase());

    try {
      // Uploading persists a claim. Navigation cancels the later read, never this write.
      const result = await request<PopResult>('/pops', { method: 'POST', body }, credentials);
      onVerified();
      if (!mounted.current) return;
      if (!result.matched_bank_line_id) {
        setState({ phase: 'complete', result, bank: null, evidenceError: null });
        return;
      }

      setState({ phase: 'loading-bank', result });
      const controller = new AbortController();
      bankRead.current = controller;
      const deadline = setTimeout(() => controller.abort(), 15000);
      try {
        const bank = await request<BankLine>(
          `/bank-lines/${encodeURIComponent(result.matched_bank_line_id)}`,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) throw new Error('Bank evidence request expired');
        if (mounted.current) setState({ phase: 'complete', result, bank, evidenceError: null });
      } catch {
        if (mounted.current)
          setState({
            phase: 'complete',
            result,
            bank: null,
            evidenceError:
              'The verification was saved, but its linked bank observation could not be loaded.',
          });
      } finally {
        clearTimeout(deadline);
        bankRead.current = null;
      }
    } catch (cause) {
      if (mounted.current)
        setState({
          phase: 'idle',
          error: cause instanceof Error ? cause.message : 'Could not verify this document.',
        });
    } finally {
      inFlight.current = false;
    }
  }

  return { state, busy, reset, verify };
}
