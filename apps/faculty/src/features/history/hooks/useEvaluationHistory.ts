import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { historyApi, type HistoryQueryParams } from '../api/history.api';

const TERMINAL_STATUSES: Record<string, true> = {
  COMPLETED: true,
  FAILED: true,
};

export function useEvaluationHistory(params: HistoryQueryParams = {}) {
  return useQuery({
    queryKey: ['history', params],
    queryFn: () => historyApi.getHistory(params),
    placeholderData: keepPreviousData,
    staleTime: 5000,
    refetchInterval: (query) => {
      const hasActiveEvaluation = query.state.data?.items.some(
        (evaluation) => !TERMINAL_STATUSES[evaluation.status],
      );
      return hasActiveEvaluation ? 2000 : false;
    },
  });
}
