import { requestJson } from '@equiped/api-client';
import type {
  TrainedAdapterListResponse,
  TrainingJobCreateResponse,
  TrainingJobListResponse,
} from '../types';

export const trainingDataApi = {
  startJob: (agentId: string) =>
    requestJson<TrainingJobCreateResponse>(`/admin/training-data/${agentId}/jobs`, {
      method: 'POST',
    }),
  listJobs: (agentId: string) =>
    requestJson<TrainingJobListResponse>(`/admin/training-data/${agentId}/jobs`),
  listAdapters: (agentId: string) =>
    requestJson<TrainedAdapterListResponse>(`/admin/training-data/${agentId}/adapters`),
};
