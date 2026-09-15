import { requestJson } from '@equiped/api-client';
import { documentsApi } from '@equiped/api-client';
import type { DocumentListResponse } from '@equiped/types';
import type { HomeEvaluationsResponse } from '../types';

export const homeApi = {
  listSlms: (): Promise<DocumentListResponse> => {
    return documentsApi.listDocuments({ sourceType: 'slm' });
  },
  listEvaluations: (pageSize = 20): Promise<HomeEvaluationsResponse> => {
    return requestJson<HomeEvaluationsResponse>(`/evaluations/?page_size=${pageSize}`);
  },
};
