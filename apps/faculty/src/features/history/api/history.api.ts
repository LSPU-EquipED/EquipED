import { evaluationsApi } from '@equiped/api-client';
import type { EvaluationListResponse, TargetAgent } from '@equiped/types';

export interface HistoryQueryParams {
  status?: string;
  target_agent?: TargetAgent | 'all';
  page?: number;
  page_size?: number;
}

export const historyApi = {
  getHistory: (params: HistoryQueryParams = {}): Promise<EvaluationListResponse> => {
    return evaluationsApi.listEvaluations({
      status: params.status,
      targetAgent: params.target_agent,
      page: params.page,
      pageSize: params.page_size,
    });
  },
};
