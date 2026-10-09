import { useQuery } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';
import type { TrainingJobListResponse } from '../types';
import { isRunActive } from '../utils/trainingData.utils';

export function jobsRefetchInterval(data: TrainingJobListResponse | undefined): number | false {
  return data?.jobs.some(isRunActive) ? 10_000 : false;
}

export function useTrainingJobs(agentId: string) {
  return useQuery({
    queryKey: ['trainingJobs', agentId],
    queryFn: () => trainingDataApi.listJobs(agentId),
    refetchInterval: (query) => jobsRefetchInterval(query.state.data),
    refetchIntervalInBackground: false,
  });
}
