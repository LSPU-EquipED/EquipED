import { requestJson } from '@equiped/api-client';
import type { MasterSynthesisDetailResponse, MatrixListResponse } from '../types';

export const matrixApi = {
  getMatrix: (
    params: { search?: string; program?: string; status?: string; page?: number; page_size?: number } = {},
  ) => {
    const searchParams = new URLSearchParams();
    if (params.search !== undefined && params.search.trim()) {
      searchParams.set('search', params.search.trim());
    }
    if (params.program) searchParams.set('program', params.program);
    if (params.status) searchParams.set('status', params.status);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));
    return requestJson<MatrixListResponse>(`/evaluations/matrix?${searchParams.toString()}`);
  },
  getMasterSynthesisDetail: (documentId: string) => {
    return requestJson<MasterSynthesisDetailResponse>(`/evaluations/matrix/${documentId}`);
  },
};
