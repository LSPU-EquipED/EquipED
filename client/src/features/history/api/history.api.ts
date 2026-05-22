import { requestJson } from '@/shared/api/http';
import type { HistoryListResponse } from '../types';

export const historyApi = {
  getHistory: (params: { status?: string; page?: number; page_size?: number } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.set('status', params.status);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));
    return requestJson<HistoryListResponse>(`/evaluations/?${searchParams.toString()}`);
  },
};
