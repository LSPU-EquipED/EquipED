import { useMutation, useQueryClient } from '@tanstack/react-query';
import { evaluationApi } from '../api/evaluation.api';
import type { CriterionFeedbackRequest } from '../types';

export function useSubmitCriterionFeedback(evaluationId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      criterionId,
      body,
    }: {
      criterionId: string;
      body: CriterionFeedbackRequest;
    }) => evaluationApi.submitCriterionFeedback(evaluationId, criterionId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['evaluation-results', evaluationId] });
      void queryClient.invalidateQueries({ queryKey: ['specialist-queue'] });
      void queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
}
