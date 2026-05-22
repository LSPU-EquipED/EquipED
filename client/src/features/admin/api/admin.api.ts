import { requestJson } from '@/shared/api/http';
import type { PromptVersionListResponse, PromptVersionItem, PromptCreateBody, PreferenceLogListResponse } from '../types';

export const adminApi = {
  getPromptVersions: (agentId: string) => requestJson<PromptVersionListResponse>(`/admin/prompts/${agentId}`),

  createPrompt: (agentId: string, body: PromptCreateBody) =>
    requestJson<PromptVersionItem>(`/admin/prompts/${agentId}`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  revertPrompt: (agentId: string, versionId: string) =>
    requestJson<PromptVersionItem>(`/admin/prompts/${agentId}/revert/${versionId}`, {
      method: 'POST',
    }),

  getPreferenceLogs: (params: { action?: string; page?: number; page_size?: number } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.action) searchParams.set('action', params.action);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));
    return requestJson<PreferenceLogListResponse>(`/admin/preferences?${searchParams.toString()}`);
  },
};
