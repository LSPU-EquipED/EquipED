import { useMutation, useQueryClient } from '@tanstack/react-query';
import { requestJson } from '@/shared/api/http';

export function useSubmitFeedback(evaluationId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { action: string; notes?: string; edited_json?: Record<string, unknown> }) =>
      requestJson(`/feedback/${evaluationId}`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evaluationResults', evaluationId] });
    },
  });
}
