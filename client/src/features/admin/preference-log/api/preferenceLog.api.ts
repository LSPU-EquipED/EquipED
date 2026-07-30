import { requestJson } from '@/shared/api/http';
import type { PreferenceLogListResponse } from '../types';

export const preferenceLogApi = {
  getPreferenceLogs: (params: { action?: string; page?: number; page_size?: number } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.action) searchParams.set('action', params.action);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));
    return requestJson<PreferenceLogListResponse>(`/admin/preferences?${searchParams.toString()}`);
  },
};
