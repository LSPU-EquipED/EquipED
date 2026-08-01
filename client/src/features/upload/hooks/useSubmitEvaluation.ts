import { useMutation, useQueryClient } from '@tanstack/react-query';
import { requestJson } from '@/shared/api/http';
import type { EvaluationResponse } from '@/features/evaluation/types';

export function useSubmitEvaluation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      document_id: string;
      partial_without_curriculum: true;
      confirmed_program: string;
    }) =>
      requestJson<EvaluationResponse>('/evaluations/', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evaluations'] });
      queryClient.invalidateQueries({ queryKey: ['evaluation'] });
    },
  });
}
