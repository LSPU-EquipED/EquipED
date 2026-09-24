import { useQuery } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';

// The dry-run costs about as much as starting a job, so fetch once per visit
// and never refetch on focus or reconnect.
export function useDatasetReadiness(agentId: string) {
  return useQuery({
    queryKey: ['datasetReadiness', agentId],
    queryFn: () => trainingDataApi.getReadiness(agentId),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}
