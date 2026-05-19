import { requestJson } from '@/shared/api/http';
import type { EvaluationResponse, EvaluationStatusResponse } from '../types';

export const evaluationApi = {
  getEvaluation: async (id: string): Promise<EvaluationResponse> => {
    return requestJson<EvaluationResponse>(`/evaluations/${id}`);
  },
  
  getEvaluationStatus: async (id: string): Promise<EvaluationStatusResponse> => {
    return requestJson<EvaluationStatusResponse>(`/evaluations/${id}/status`);
  }
};
