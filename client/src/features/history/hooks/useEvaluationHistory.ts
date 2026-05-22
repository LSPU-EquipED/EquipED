import { useQuery } from '@tanstack/react-query';
import { historyApi } from '../api/history.api';

export function useEvaluationHistory(params: { status?: string; page?: number; page_size?: number } = {}) {
  return useQuery({
    queryKey: ['history', params],
    queryFn: () => historyApi.getHistory(params),
  });
}
