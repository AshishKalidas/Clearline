import { useEffect, useRef, useState } from 'react';
import { ApiError, type CsvIssue, type WorkspaceRequest } from '../api';
import type { Credentials } from '../types';
import type { ImportKind, ImportPreview, ImportResult } from './templates';

interface ImportProblem {
  message: string;
  issues: CsvIssue[];
  issueCount: number;
}
interface SelectedFile {
  kind: ImportKind;
  file: File;
}
type ImportState =
  | { phase: 'idle'; kind: ImportKind; file: File | null; problem: ImportProblem | null }
  | (SelectedFile & { phase: 'validating' })
  | (SelectedFile & {
      phase: 'ready';
      preview: ImportPreview;
      confirmed: boolean;
      problem: ImportProblem | null;
    })
  | (SelectedFile & { phase: 'importing'; preview: ImportPreview })
  | (SelectedFile & { phase: 'done'; preview: ImportPreview; result: ImportResult });

interface ImportOptions {
  enabled: boolean;
  request: WorkspaceRequest;
  credentials: Credentials;
  onImported: () => void;
}
function problemFrom(cause: unknown): ImportProblem {
  return {
    message:
      cause instanceof Error ? cause.message : 'The import could not be completed. Please retry.',
    issues: cause instanceof ApiError ? cause.issues : [],
    issueCount: cause instanceof ApiError ? cause.issueCount : 0,
  };
}

/** A preview belongs to one immutable file/type pair; only a confirmed ready state can write. */
export function useCsvImport({ enabled, request, credentials, onImported }: ImportOptions) {
  const [state, setState] = useState<ImportState>({
    phase: 'idle',
    kind: 'invoices',
    file: null,
    problem: null,
  });
  const pendingPreview = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  // State updates render asynchronously. This lock also rejects repeated calls in the same event.
  const inFlight = useRef(false);
  const busy = state.phase === 'validating' || state.phase === 'importing';
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      pendingPreview.current?.abort();
    };
  }, []);

  function selectKind(kind: ImportKind) {
    if (!inFlight.current) setState({ phase: 'idle', kind, file: null, problem: null });
  }
  function selectFile(file: File | null) {
    if (!inFlight.current) setState({ phase: 'idle', kind: state.kind, file, problem: null });
  }
  function confirm(confirmed: boolean) {
    setState((previous) => (previous.phase === 'ready' ? { ...previous, confirmed } : previous));
  }
  async function validate() {
    if (!enabled || !mounted.current || inFlight.current || !state.file || state.phase === 'done')
      return;
    const selection = { kind: state.kind, file: state.file };
    if (selection.file.size > 5_000_000) {
      setState({
        ...selection,
        phase: 'idle',
        problem: problemFrom(new Error('Choose a CSV no larger than 5 MB.')),
      });
      return;
    }
    inFlight.current = true;
    const controller = new AbortController();
    pendingPreview.current = controller;
    setState({ ...selection, phase: 'validating' });
    const deadline = setTimeout(() => controller.abort(), 15000);
    const body = new FormData();
    body.append('file', selection.file);
    try {
      const preview = await request<ImportPreview>(
        `/ingest/${selection.kind}/preview`,
        { method: 'POST', body, signal: controller.signal },
        credentials,
      );
      if (controller.signal.aborted) throw new Error('Preview expired');
      if (mounted.current)
        setState({ ...selection, phase: 'ready', preview, confirmed: false, problem: null });
    } catch (cause) {
      if (mounted.current)
        setState({
          ...selection,
          phase: 'idle',
          problem: problemFrom(
            controller.signal.aborted
              ? new Error('Validation took too long. Try a smaller file or retry.')
              : cause,
          ),
        });
    } finally {
      clearTimeout(deadline);
      pendingPreview.current = null;
      inFlight.current = false;
    }
  }
  async function importFile() {
    if (
      !enabled ||
      !mounted.current ||
      inFlight.current ||
      state.phase !== 'ready' ||
      !state.confirmed
    )
      return;
    inFlight.current = true;
    const ready = state;
    setState({ phase: 'importing', kind: ready.kind, file: ready.file, preview: ready.preview });
    const body = new FormData();
    body.append('file', ready.file);
    try {
      // Once submitted, a write may finish after navigation. Only previews are cancelled.
      const result = await request<ImportResult>(
        `/ingest/${ready.kind}`,
        { method: 'POST', body },
        credentials,
      );
      if (mounted.current)
        setState({
          phase: 'done',
          kind: ready.kind,
          file: ready.file,
          preview: ready.preview,
          result,
        });
      onImported();
    } catch (cause) {
      if (mounted.current) setState({ ...ready, problem: problemFrom(cause) });
    } finally {
      inFlight.current = false;
    }
  }
  return { state, busy, selectKind, selectFile, confirm, validate, importFile };
}
