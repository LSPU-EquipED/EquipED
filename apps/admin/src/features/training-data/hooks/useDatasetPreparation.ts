import { useDatasetReadiness } from './useDatasetReadiness';
import { useTrainingJobs } from './useTrainingJobs';
import {
  compareToLatestJob,
  describeComparison,
  getReadinessTier,
  getReviewerNote,
} from '../utils/trainingData.utils';

export function useDatasetPreparation(agentId: string) {
  const { data, isLoading, isError, refetch } = useDatasetReadiness(agentId);
  const { data: jobsData } = useTrainingJobs(agentId);

  return {
    data,
    isLoading,
    isError,
    refetch,
    readiness: data ? getReadinessTier(data.pair_count, data.evaluation_count) : null,
    comparison: data ? describeComparison(compareToLatestJob(data, jobsData?.jobs[0])) : null,
    reviewerNote: data ? getReviewerNote(data.reviewer_count) : null,
  };
}
