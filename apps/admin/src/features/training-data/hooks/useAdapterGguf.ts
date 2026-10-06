import { useMutation, useQueryClient } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

function useRefreshAdapters(agentId: string) {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: ['trainedAdapters', agentId] });
  };
}

export function useUploadGguf(agentId: string, adapterId: string) {
  const refresh = useRefreshAdapters(agentId);
  return useMutation({
    mutationFn: ({ file, replace }: { file: File; replace: boolean }) =>
      trainingDataApi.uploadGguf(agentId, adapterId, file, replace),
    onSettled: refresh,
  });
}

export function useRemoveGguf(agentId: string, adapterId: string) {
  const refresh = useRefreshAdapters(agentId);
  return useMutation({
    mutationFn: () => trainingDataApi.deleteGguf(agentId, adapterId),
    onSettled: refresh,
  });
}

export function useGgufDownloadLink(agentId: string, adapterId: string) {
  const refresh = useRefreshAdapters(agentId);
  return useMutation({
    mutationFn: (hours: number) =>
      trainingDataApi.createGgufDownloadLink(agentId, adapterId, hours),
    onSettled: refresh,
  });
}
