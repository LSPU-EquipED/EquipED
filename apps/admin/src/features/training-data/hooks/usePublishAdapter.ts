import { useMutation, useQueryClient } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

export function usePublishAdapter(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (adapterId: string) => trainingDataApi.publishAdapter(agentId, adapterId),
    onSettled: () => {
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
    onSettled: () => {
      void queryClient.invalidateQueries({
        queryKey: ['trainedAdapters', agentId],
      });
    },
  });
}
