import { useMutation, useQueryClient } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';
import type { TrainingJobCreateResponse } from '../types';

export function useStartTrainingJob(onCreated: (credentials: TrainingJobCreateResponse) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (agentId: string) => trainingDataApi.startJob(agentId),
    onSuccess: (credentials) => {
      // Keep the handoff even if the user switches specialist while creation is pending.
      onCreated(credentials);
      void queryClient.invalidateQueries({
        queryKey: ['trainingJobs', credentials.agent_id],
      });
    },
  });
}
