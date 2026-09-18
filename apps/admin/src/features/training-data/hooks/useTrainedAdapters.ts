import { useQuery } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

export function useTrainedAdapters(agentId: string) {
  return useQuery({
    queryKey: ['trainedAdapters', agentId],
    queryFn: () => trainingDataApi.listAdapters(agentId),
  });
}
