import { requestJson } from '@/shared/api/http';
import type {
  RubricActivationOut,
  RubricCriterion,
  RubricCriterionCreate,
  RubricCriterionMoveRequest,
  RubricCriterionUpdate,
  RubricDomain,
  RubricDomainCreate,
  RubricDomainUpdate,
  RubricPublishRequest,
  RubricReorderRequest,
  RubricRevisionsResponse,
  RubricSet,
  RubricSetListResponse,
  ValidationReport,
} from '../types';

export const rubricEditorApi = {
  getRubricSets: (params?: { all_revisions?: boolean; agent_id?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.all_revisions) searchParams.set('all_revisions', 'true');
    if (params?.agent_id) searchParams.set('agent_id', params.agent_id);
    const query = searchParams.toString();
    return requestJson<RubricSetListResponse>(`/admin/rubrics${query ? `?${query}` : ''}`);
  },

  getRevisions: (agentId?: string) => {
    const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : '';
    return requestJson<RubricRevisionsResponse>(`/admin/rubrics/revisions${query}`);
  },

  getRubricSetById: (rubricSetId: string) =>
    requestJson<RubricSet>(`/admin/rubrics/${rubricSetId}`),

  createDraft: (agentId: string) =>
    requestJson<RubricSet>(`/admin/rubrics/agents/${agentId}/draft`, {
      method: 'POST',
    }),

  deleteDraft: (rubricSetId: string) =>
    requestJson<void>(`/admin/rubrics/${rubricSetId}/draft`, {
      method: 'DELETE',
    }),

  validateDraft: (rubricSetId: string) =>
    requestJson<ValidationReport>(`/admin/rubrics/${rubricSetId}/validate`, {
      method: 'POST',
    }),

  publishRevision: (rubricSetId: string, activate: boolean = true) =>
    requestJson<RubricSet>(`/admin/rubrics/${rubricSetId}/publish`, {
      method: 'POST',
      body: JSON.stringify({ activate } satisfies RubricPublishRequest),
    }),

  activateRevision: (rubricSetId: string) =>
    requestJson<RubricActivationOut>(`/admin/rubrics/${rubricSetId}/activate`, {
      method: 'POST',
    }),

  retireRevision: (rubricSetId: string) =>
    requestJson<RubricSet>(`/admin/rubrics/${rubricSetId}/retire`, {
      method: 'POST',
    }),

  reorderRubricTree: (rubricSetId: string, body: RubricReorderRequest) =>
    requestJson<RubricSet>(`/admin/rubrics/${rubricSetId}/reorder`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  createDomain: (rubricSetId: string, body: RubricDomainCreate) =>
    requestJson<RubricDomain>(`/admin/rubrics/${rubricSetId}/domains`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateDomain: (domainId: string, body: RubricDomainUpdate) =>
    requestJson<RubricDomain>(`/admin/rubrics/domains/${domainId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteDomain: (domainId: string) =>
    requestJson<void>(`/admin/rubrics/domains/${domainId}`, {
      method: 'DELETE',
    }),

  createCriterion: (domainId: string, body: RubricCriterionCreate) =>
    requestJson<RubricCriterion>(`/admin/rubrics/domains/${domainId}/criteria`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateCriterion: (criterionId: string, body: RubricCriterionUpdate) =>
    requestJson<RubricCriterion>(`/admin/rubrics/criteria/${criterionId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  moveCriterion: (criterionId: string, body: RubricCriterionMoveRequest) =>
    requestJson<RubricCriterion>(`/admin/rubrics/criteria/${criterionId}/move`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  deleteCriterion: (criterionId: string) =>
    requestJson<void>(`/admin/rubrics/criteria/${criterionId}`, {
      method: 'DELETE',
    }),
};
