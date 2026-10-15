import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { request as httpRequest, type WorkspaceRequest } from '../api';
import type { ActivityEvent, BankLine, Metrics, Proposal, WorkspaceMode } from '../types';
import { createSampleClient } from './sample';

export interface Snapshot {
  queue: Proposal[];
  bankLines: BankLine[];
  metrics: Metrics | null;
  activity: ActivityEvent[];
  updatedAt: Date | null;
  error: string | null;
  loading: boolean;
  refreshing: boolean;
}
interface WorkspaceContextValue {
  mode: WorkspaceMode;
  basePath: string;
  request: WorkspaceRequest;
  snapshot: Snapshot;
  revision: number;
  reload: () => void;
  polling: boolean;
  setPolling: (value: boolean) => void;
  resetSample: () => void;
}
const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);
const initialSnapshot: Snapshot = {
  queue: [],
  bankLines: [],
  metrics: null,
  activity: [],
  updatedAt: null,
  error: null,
  loading: true,
  refreshing: false,
};

/** One workspace owns its data source. Changing modes unmounts it and aborts pending reads. */
export function WorkspaceProvider({
  mode,
  children,
}: {
  mode: WorkspaceMode;
  children: ReactNode;
}) {
  const sample = useMemo(() => (mode === 'sample' ? createSampleClient() : null), [mode]);
  const request = sample?.request ?? httpRequest;
  const [snapshot, setSnapshot] = useState<Snapshot>(initialSnapshot);
  const [revision, setRevision] = useState(0);
  const [polling, setPolling] = useState(true);
  const lastRevision = useRef(-1);
  const reload = useCallback(() => setRevision((version) => version + 1), []);
  const resetSample = useCallback(() => {
    sample?.reset();
    reload();
  }, [sample, reload]);

  useEffect(() => {
    const manual = lastRevision.current !== revision;
    lastRevision.current = revision;
    if (!polling && !manual) {
      setSnapshot((previous) => ({ ...previous, loading: false, refreshing: false }));
      return;
    }
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController;
    let deadline: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      controller = new AbortController();
      deadline = setTimeout(() => controller.abort(), 8000);
      setSnapshot((previous) => ({ ...previous, refreshing: true }));
      try {
        const options = { signal: controller.signal };
        const [, metrics, queue, bankLines, activity] = await Promise.all([
          request('/healthz', options),
          request<Metrics>('/metrics', options),
          request<Proposal[]>('/proposals', options),
          request<BankLine[]>('/bank-lines?limit=1000', options),
          request<ActivityEvent[]>('/activity?limit=20', options),
        ]);
        if (!disposed)
          setSnapshot({
            queue,
            bankLines,
            metrics,
            activity,
            updatedAt: new Date(),
            loading: false,
            refreshing: false,
            error: null,
          });
      } catch (error) {
        controller.abort();
        if (!disposed)
          setSnapshot((previous) => ({
            ...previous,
            loading: false,
            refreshing: false,
            error:
              error instanceof Error && error.name !== 'AbortError'
                ? error.message
                : 'The workspace did not respond in time. Check the API and retry.',
          }));
      } finally {
        clearTimeout(deadline);
        if (!disposed && mode === 'connected' && polling) timer = setTimeout(load, 10000);
      }
    }
    void load();
    return () => {
      disposed = true;
      controller?.abort();
      clearTimeout(timer);
      clearTimeout(deadline);
    };
  }, [mode, request, revision, polling]);

  const value = useMemo(
    () => ({
      mode,
      request,
      snapshot,
      revision,
      reload,
      polling,
      setPolling,
      resetSample,
      basePath: mode === 'sample' ? '/sample' : '/workspace',
    }),
    [mode, request, snapshot, revision, reload, polling, resetSample],
  );
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}
export function useWorkspace() {
  const workspace = useContext(WorkspaceContext);
  if (!workspace) throw new Error('This view requires a workspace.');
  return workspace;
}
/** Leaves standalone component tests and consumers on the real HTTP adapter by default. */
export function useWorkspaceRequest(): WorkspaceRequest {
  return useContext(WorkspaceContext)?.request ?? httpRequest;
}
