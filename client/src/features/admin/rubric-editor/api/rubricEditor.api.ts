import { requestJson } from '@/shared/api/http';
import type {
  CriterionTextUpdate,
  DomainTitleUpdate,
  RubricCriterion,
  RubricDomain,
  RubricSetListResponse,
} from '../types';

export const rubricEditorApi = {
  getRubricSets: () => requestJson<RubricSetListResponse>('/admin/rubrics'),

  updateCriterion: (criterionId: string, body: CriterionTextUpdate) =>
    requestJson<RubricCriterion>(`/admin/rubrics/criteria/${criterionId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  updateDomain: (domainId: string, body: DomainTitleUpdate) =>
    requestJson<RubricDomain>(`/admin/rubrics/domains/${domainId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
};
