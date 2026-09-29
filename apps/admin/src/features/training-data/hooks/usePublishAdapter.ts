import { useMutation, useQueryClient } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

export function usePublishAdapter(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (adapterId: string) => trainingDataApi.publishAdapter(agentId, adapterId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['trainedAdapters', agentId],
      });
    },
  });
}

export function useUnpublishAdapter(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => trainingDataApi.unpublishAdapter(agentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['trainedAdapters', agentId],
      });
    },
  });
}
