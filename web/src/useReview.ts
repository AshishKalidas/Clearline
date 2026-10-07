import { useCallback, useEffect, useState } from 'react';
import { request } from './api';
import type { Metrics, Proposal, ProposalDetail } from './types';

/** Keep selection stable during refresh and cancel stale evidence requests. */
export function useReview() {
  const [queue, setQueue] = useState<Proposal[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ProposalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const [proposals, summary] = await Promise.all([
        request<Proposal[]>('/proposals'),
        request<Metrics>('/metrics'),
      ]);
      setQueue(proposals);
      setMetrics(summary);
      setSelectedId((current) =>
        proposals.some((p) => p.id === current) ? current : (proposals[0]?.id ?? null),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load the review queue.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);
  useEffect(() => {
    const controller = new AbortController();
    setDetail(null);
    if (!selectedId) {
      setDetailLoading(false);
      return;
    }
    setDetailLoading(true);
    request<ProposalDetail>(`/proposals/${selectedId}`, { signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) setDetail(result);
      })
      .catch((e) => {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : 'Could not load evidence.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setDetailLoading(false);
      });
    return () => controller.abort();
  }, [selectedId]);
  return {
    queue,
    metrics,
    selectedId,
    setSelectedId,
    detail,
    loading,
    detailLoading,
    error,
    setError,
    reload,
  };
}
