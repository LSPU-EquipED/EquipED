import { requestJson } from '@/shared/api/http';
import type { HistoryListResponse } from '../types';

export interface HistoryQueryParams {
  status?: string;
  target_agent?: string;
  page?: number;
  page_size?: number;
}

export const historyApi = {
  getHistory: (params: HistoryQueryParams = {}) => {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.set('status', params.status);
    if (params.target_agent) searchParams.set('target_agent', params.target_agent);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));
    return requestJson<HistoryListResponse>(`/evaluations/?${searchParams.toString()}`);
  },
};
