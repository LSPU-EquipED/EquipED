import { useQuery } from '@tanstack/react-query';
import { evaluationApi } from '../api/evaluation.api';
import type { EvaluationResponse } from '../types';

export function useEvaluation(id: string) {
  return useQuery<EvaluationResponse>({
    queryKey: ['evaluation', id],
    queryFn: () => evaluationApi.getEvaluation(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'COMPLETED' || status === 'FAILED') {
        return false;
      }
      return 3000; // Poll every 3 seconds
    },
  });
}
