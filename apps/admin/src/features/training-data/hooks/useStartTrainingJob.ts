import { useMutation, useQueryClient } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

export function useStartTrainingJob(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => trainingDataApi.startJob(agentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['trainingJobs', agentId] });
    },
  });
}
