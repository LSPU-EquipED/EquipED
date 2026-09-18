import { useQuery } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

export function useTrainingJobs(agentId: string) {
  return useQuery({
    queryKey: ['trainingJobs', agentId],
    queryFn: () => trainingDataApi.listJobs(agentId),
  });
}
