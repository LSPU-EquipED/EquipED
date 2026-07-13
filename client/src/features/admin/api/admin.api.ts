import { buildApiUrl, requestJson } from '@/shared/api/http';
import {
  mapDocumentUploadResponse,
  mapPolicyDeleteResponse,
  mapPolicyLibraryResponse,
  mapPolicyRebuildResponse,
  mapReferenceDeleteResponse,
  mapReferenceLibraryResponse,
  mapReferenceRebuildResponse,
  type RawDocumentUploadResponse,
  type RawPolicyDeleteResponse,
  type RawPolicyLibraryResponse,
  type RawPolicyRebuildResponse,
  type RawReferenceDeleteResponse,
  type RawReferenceLibraryResponse,
  type RawReferenceRebuildResponse,
  type PolicyDeleteResponse,
  type PolicyLibraryResponse,
  type PolicyRebuildResponse,
  type ReferenceDeleteResponse,
  type ReferenceRebuildResponse,
  type ReferenceLibraryResponse,
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
  ModelValidationCreateBody,
  ModelValidationCriteriaResponse,
  ModelValidationItem,
  ModelValidationListResponse,
  ModelValidationMetricsResponse,
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

    if (input.program && input.program.trim()) {
      formData.append('program', input.program.trim().toUpperCase());
    }

    if (input.sourceType === 'policy' && input.policyArea) {
      formData.append('policy_area', input.policyArea);
    }

    const response = await requestJson<RawDocumentUploadResponse>('/documents/upload', {
      method: 'POST',
      body: formData,
    });

    return mapDocumentUploadResponse(response);
  },

  getReferences: async (): Promise<ReferenceLibraryResponse> => {
    const response = await requestJson<RawReferenceLibraryResponse>('/documents/references');
    return mapReferenceLibraryResponse(response);
  },

  getReferenceFileUrl: (documentId: string): string => {
    return buildApiUrl(`/documents/${documentId}/file`);
  },

  deleteReference: async (documentId: string): Promise<ReferenceDeleteResponse> => {
    const response = await requestJson<RawReferenceDeleteResponse>(`/documents/${documentId}`, {
      method: 'DELETE',
    });
    return mapReferenceDeleteResponse(response);
  },

  rebuildReferenceEmbeddings: async (documentId: string): Promise<ReferenceRebuildResponse> => {
    const response = await requestJson<RawReferenceRebuildResponse>(
      `/documents/${documentId}/rebuild-embeddings`,
      {
        method: 'POST',
      },
    );
    return mapReferenceRebuildResponse(response);
  },

  getPolicies: async (): Promise<PolicyLibraryResponse> => {
    const response = await requestJson<RawPolicyLibraryResponse>('/documents/policies');
    return mapPolicyLibraryResponse(response);
  },

  deletePolicy: async (documentId: string): Promise<PolicyDeleteResponse> => {
    const response = await requestJson<RawPolicyDeleteResponse>(
      `/documents/policies/${documentId}`,
      { method: 'DELETE' },
    );
    return mapPolicyDeleteResponse(response);
  },

  rebuildPolicyEmbeddings: async (documentId: string): Promise<PolicyRebuildResponse> => {
    const response = await requestJson<RawPolicyRebuildResponse>(
      `/documents/policies/${documentId}/rebuild-embeddings`,
      { method: 'POST' },
    );
    return mapPolicyRebuildResponse(response);
  },

  createModelValidation: (body: ModelValidationCreateBody) =>
    requestJson<ModelValidationItem>('/admin/model-validations', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getModelValidations: () => requestJson<ModelValidationListResponse>('/admin/model-validations'),

  getModelValidationMetrics: () =>
    requestJson<ModelValidationMetricsResponse>('/admin/model-validations/metrics'),

  getModelValidationCriteria: () =>
    requestJson<ModelValidationCriteriaResponse>('/admin/model-validations/criteria'),
};
