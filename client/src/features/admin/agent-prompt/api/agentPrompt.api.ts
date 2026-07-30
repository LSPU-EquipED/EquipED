import { requestJson } from '@/shared/api/http';
import type { PromptCreateBody, PromptVersionItem, PromptVersionListResponse } from '../types';

export const agentPromptApi = {
  getPromptVersions: (agentId: string) =>
    requestJson<PromptVersionListResponse>(`/admin/prompts/${agentId}`),

  createPrompt: (agentId: string, body: PromptCreateBody) =>
    requestJson<PromptVersionItem>(`/admin/prompts/${agentId}`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  revertPrompt: (agentId: string, versionId: string) =>
    requestJson<PromptVersionItem>(`/admin/prompts/${agentId}/revert/${versionId}`, {
      method: 'POST',
    }),
};
