import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { evaluationsApi } from '@/shared/api/evaluations.api';
import type { LatestEvaluationItem } from '@/shared/types/evaluations';
import { isEvaluatingStatus } from '@/shared/utils/slmDisplayStatus';

export function isEvaluationStatusActive(status: string | null | undefined): boolean {
  return isEvaluatingStatus(status);
}

export function useLatestEvaluations(documentIds: string[]) {
  // Deduplicate and sort IDs for a stable query key
  const stableIds = useMemo(() => {
    return Array.from(new Set(documentIds.filter(Boolean))).sort();
  }, [documentIds]);

  const query = useQuery({
    queryKey: ['evaluations', 'latest', stableIds],
    queryFn: () => evaluationsApi.getLatestEvaluations(stableIds),
    enabled: stableIds.length > 0,
    refetchInterval: (q) => {
      const items = q.state.data?.items ?? [];
      const hasActive = items.some((item) => isEvaluatingStatus(item.status));
      return hasActive ? 4000 : false;
    },
  });

  // Map response items into a lookup map by document_id
  // Ensure repeated failed/evaluation attempts collapse to the latest state per SLM
  const latestEvalsByDocId = useMemo<Record<string, LatestEvaluationItem>>(() => {
    const map: Record<string, LatestEvaluationItem> = {};
    const items = query.data?.items ?? [];
    for (const item of items) {
      if (!item.document_id) continue;
      const existing = map[item.document_id];
      if (!existing) {
        map[item.document_id] = item;
      } else {
        const existingTime = new Date(existing.submitted_at).getTime();
        const itemTime = new Date(item.submitted_at).getTime();
        if (isNaN(existingTime) || itemTime >= existingTime) {
          map[item.document_id] = item;
        }
      }
    }
    return map;
  }, [query.data?.items]);

  const hasActiveEvaluations = useMemo(() => {
    return (query.data?.items ?? []).some((item) => isEvaluatingStatus(item.status));
  }, [query.data?.items]);

  return {
    ...query,
    latestEvalsByDocId,
    hasActiveEvaluations,
  };
}
