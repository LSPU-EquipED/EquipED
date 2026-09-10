import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { evaluationApi } from '../api/evaluation.api';
import type { DeskQueueListResponse, DeskQueueItem } from '../types';
import type { TargetAgent } from '@/shared/types/evaluations';

export interface UseSpecialistQueueOptions {
  enabled?: boolean;
  refetchInterval?: number | false;
}

export function useSpecialistQueue(
  targetAgent: TargetAgent,
  program?: string,
  options?: UseSpecialistQueueOptions,
): UseQueryResult<DeskQueueListResponse, Error> {
  return useQuery<DeskQueueListResponse, Error>({
    queryKey: ['specialist-queue', targetAgent, program],
    queryFn: async () => {
      if (typeof evaluationApi?.getDeskQueue !== 'function') {
        return { items: [], total: 0 };
      }
      return evaluationApi.getDeskQueue(targetAgent, program);
    },
    enabled: options?.enabled ?? Boolean(targetAgent),
    staleTime: 10000,
    refetchInterval: (query) => {
      if (options?.refetchInterval !== undefined) {
        return options.refetchInterval;
      }
      const hasEvaluating = query.state.data?.items?.some(
        (item: DeskQueueItem) => item.my_status === 'EVALUATING',
      );
      return hasEvaluating ? 3000 : false;
    },
  });
}
