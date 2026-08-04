import { useQuery } from '@tanstack/react-query';
import { historyApi } from '../api/history.api';

const TERMINAL_STATUSES = new Set(['COMPLETED', 'FAILED']);

export function useEvaluationHistory(
  params: { status?: string; page?: number; page_size?: number } = {},
) {
  return useQuery({
    queryKey: ['history', params],
    queryFn: () => historyApi.getHistory(params),
    refetchInterval: (query) => {
      const hasActiveEvaluation = query.state.data?.items.some(
        (evaluation) => !TERMINAL_STATUSES.has(evaluation.status),
      );
      return hasActiveEvaluation ? 2000 : false;
    },
  });
}
