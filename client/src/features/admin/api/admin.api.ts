import { requestJson } from '@/shared/api/http';
import {
  mapDocumentUploadResponse,
  type RawDocumentUploadResponse,
} from '@/shared/types/documents';
import type {
  PromptVersionListResponse,
  PromptVersionItem,
  PromptCreateBody,
  PreferenceLogListResponse,
  AdminUserListResponse,
  AdminUserResponse,
  AdminUserCreateBody,
  AdminUserUpdateBody,
  SystemSummaryResponse,
  MatrixListResponse,
  AdminUploadInput,
} from '../types';

export const adminApi = {
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

  getPreferenceLogs: (params: { action?: string; page?: number; page_size?: number } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.action) searchParams.set('action', params.action);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));
    return requestJson<PreferenceLogListResponse>(`/admin/preferences?${searchParams.toString()}`);
  },

  getSummary: () => requestJson<SystemSummaryResponse>('/admin/summary'),

  getUsers: () => requestJson<AdminUserListResponse>('/admin/users'),

  createUser: (body: AdminUserCreateBody) =>
    requestJson<AdminUserResponse>('/admin/users', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateUser: (userId: string, body: AdminUserUpdateBody) =>
    requestJson<AdminUserResponse>(`/admin/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deactivateUser: (userId: string) =>
    requestJson<void>(`/admin/users/${userId}`, {
      method: 'DELETE',
    }),

  hardDeleteUser: (userId: string) =>
    requestJson<void>(`/admin/users/${userId}/permanent`, {
      method: 'DELETE',
    }),

  getMatrix: (
    params: { program?: string; status?: string; page?: number; page_size?: number } = {},
  ) => {
    const searchParams = new URLSearchParams();
    if (params.program) searchParams.set('program', params.program);
    if (params.status) searchParams.set('status', params.status);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));
    return requestJson<MatrixListResponse>(`/evaluations/matrix?${searchParams.toString()}`);
  },

  uploadReferenceDocument: async (input: AdminUploadInput) => {
    const formData = new FormData();
    formData.append('file', input.file);
    formData.append('source_type', input.sourceType);
    formData.append('title', input.title.trim());

    const response = await requestJson<RawDocumentUploadResponse>('/documents/upload', {
      method: 'POST',
      body: formData,
    });

    return mapDocumentUploadResponse(response);
  },
};
