import { requestJson } from '@/shared/api/http';
import { documentsApi } from '@/shared/api/documents.api';
import type { DocumentListResponse } from '@/shared/types/documents';
import type { HomeEvaluationsResponse } from '../types';

export const homeApi = {
  listSlms: (): Promise<DocumentListResponse> => {
    return documentsApi.listDocuments({ sourceType: 'slm' });
  },
  listEvaluations: (pageSize = 20): Promise<HomeEvaluationsResponse> => {
    return requestJson<HomeEvaluationsResponse>(`/evaluations/?page_size=${pageSize}`);
  },
};
