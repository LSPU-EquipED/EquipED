import { useMutation, useQueryClient } from '@tanstack/react-query';
import { evaluationApi } from '../api/evaluation.api';
import type { EvaluationResponse, EvaluationSubmitRequest } from '../types';

export function useSubmitEvaluation() {
  const queryClient = useQueryClient();

  return useMutation<EvaluationResponse, Error, EvaluationSubmitRequest>({
    mutationFn: (data: EvaluationSubmitRequest) => evaluationApi.submitEvaluation(data),
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
      void queryClient.invalidateQueries({ queryKey: ['documents'] });
      void queryClient.invalidateQueries({ queryKey: ['latest-evaluations'] });
    },
  });
}
