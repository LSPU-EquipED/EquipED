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
    onSuccess: (evaluation) => {
      // Make the accepted job visible to the evaluation interface immediately;
      // the backend list remains authoritative on subsequent refreshes.
      queryClient.setQueryData(
        ['resolve-evaluation', evaluation.document_id],
        evaluation.evaluation_id,
      );
      queryClient.setQueryData(['evaluation-status', evaluation.evaluation_id], {
        evaluation_id: evaluation.evaluation_id,
        status: evaluation.status,
        error_message: evaluation.error_message,
        partial_without_curriculum: evaluation.partial_without_curriculum,
        partial_reason: evaluation.partial_reason,
        completed_at: evaluation.completed_at,
        duration_seconds: evaluation.duration_seconds,
      });

      void queryClient.invalidateQueries({ queryKey: ['evaluations'] });
      void queryClient.invalidateQueries({ queryKey: ['evaluation'] });
      void queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
}
