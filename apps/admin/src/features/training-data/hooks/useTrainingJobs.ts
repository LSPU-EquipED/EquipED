import { useQuery } from '@tanstack/react-query';
import { trainingDataApi } from '../api/trainingData.api';
import type { TrainingJobListResponse } from '../types';
import { shouldPollRun } from '../utils/trainingData.utils';

export function jobsRefetchInterval(
  data: TrainingJobListResponse | undefined,
  now: number = Date.now(),
): number | false {
  return data?.jobs.some((job) => shouldPollRun(job, now)) ? 10_000 : false;
}

export function useTrainingJobs(agentId: string) {
  return useQuery({
    queryKey: ['trainingJobs', agentId],
    queryFn: () => trainingDataApi.listJobs(agentId),
    refetchInterval: (query) => jobsRefetchInterval(query.state.data),
    refetchIntervalInBackground: false,
    // Coming back from Colab should show the new state without a manual reload.
    refetchOnWindowFocus: true,
  });
}
