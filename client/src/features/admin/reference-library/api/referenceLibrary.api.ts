import { buildApiUrl, requestJson } from '@/shared/api/http';
import {
  mapPolicyDeleteResponse,
  mapPolicyLibraryResponse,
  mapPolicyRebuildResponse,
  mapReferenceDeleteResponse,
  mapReferenceLibraryResponse,
  mapReferenceRebuildResponse,
  type PolicyDeleteResponse,
  type PolicyLibraryResponse,
  type PolicyRebuildResponse,
  type RawPolicyDeleteResponse,
  type RawPolicyLibraryResponse,
  type RawPolicyRebuildResponse,
  type RawReferenceDeleteResponse,
  type RawReferenceLibraryResponse,
  type RawReferenceRebuildResponse,
  type ReferenceDeleteResponse,
  type ReferenceLibraryResponse,
  type ReferenceRebuildResponse,
} from '../types';

export const referenceLibraryApi = {
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
};
