import { requestJson } from '@equiped/api-client';
import type {
  DatasetReadiness,
  GgufDownloadLink,
  HostKeyCreated,
  HostSyncState,
  TrainedAdapterItem,
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
  getReadiness: (agentId: string) =>
    requestJson<DatasetReadiness>(`/admin/training-data/${agentId}/readiness`),
  listAdapters: (agentId: string) =>
    requestJson<TrainedAdapterListResponse>(`/admin/training-data/${agentId}/adapters`),
  publishAdapter: (agentId: string, adapterId: string) =>
    requestJson<TrainedAdapterListResponse>(`/admin/training-data/${agentId}/published`, {
      method: 'PUT',
      body: JSON.stringify({ adapter_id: adapterId }),
    }),
  unpublishAdapter: (agentId: string) =>
    requestJson<void>(`/admin/training-data/${agentId}/published`, {
      method: 'DELETE',
    }),
  uploadGguf: (agentId: string, adapterId: string, file: File, replace: boolean) => {
    const formData = new FormData();
    formData.append('file', file);
    return requestJson<TrainedAdapterItem>(
      `/admin/training-data/${agentId}/adapters/${adapterId}/gguf?replace=${replace}`,
      { method: 'POST', body: formData },
    );
  },
  createGgufDownloadLink: (agentId: string, adapterId: string, hours: number) =>
    requestJson<GgufDownloadLink>(
      `/admin/training-data/${agentId}/adapters/${adapterId}/gguf/download-link`,
      { method: 'POST', body: JSON.stringify({ expires_in_hours: hours }) },
    ),
  deleteGguf: (agentId: string, adapterId: string) =>
    requestJson<void>(`/admin/training-data/${agentId}/adapters/${adapterId}/gguf`, {
      method: 'DELETE',
    }),
  getHostSync: () => requestJson<HostSyncState>('/admin/training-data/host'),
  createHostKey: () =>
    requestJson<HostKeyCreated>('/admin/training-data/host/key', { method: 'POST' }),
  revokeHostKey: () => requestJson<void>('/admin/training-data/host/key', { method: 'DELETE' }),
};
