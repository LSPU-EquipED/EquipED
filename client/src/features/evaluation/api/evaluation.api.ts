import { requestJson } from '@/shared/api/http';
import type {
  EvaluationResponse,
  EvaluationResultsResponse,
  EvaluationStatusResponse,
  EvaluationListResponse,
  CriterionFeedbackRequest,
  CriterionFeedbackResponse,
} from '../types';

export const evaluationApi = {
  listEvaluations: async (documentId?: string): Promise<EvaluationListResponse> => {
    const params = documentId ? `?document_id=${encodeURIComponent(documentId)}` : '';
    return requestJson<EvaluationListResponse>(`/evaluations/${params}`);
  },

  getEvaluation: async (id: string): Promise<EvaluationResponse> => {
    return requestJson<EvaluationResponse>(`/evaluations/${id}`);
  },

  getEvaluationStatus: async (id: string): Promise<EvaluationStatusResponse> => {
    return requestJson<EvaluationStatusResponse>(`/evaluations/${id}/status`);
  },

  getEvaluationResults: async (id: string): Promise<EvaluationResultsResponse> => {
    return requestJson<EvaluationResultsResponse>(`/evaluations/${id}/results`);
  },

  submitCriterionFeedback: async (
    evaluationId: string,
    criterionId: string,
    body: CriterionFeedbackRequest,
  ): Promise<CriterionFeedbackResponse> => {
    return requestJson<CriterionFeedbackResponse>(
      `/feedback/${evaluationId}/criteria/${encodeURIComponent(criterionId)}`,
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
    );
  },
};
