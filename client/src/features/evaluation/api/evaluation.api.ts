import { requestJson } from '@/shared/api/http';
import type {
  EvaluationResponse,
  EvaluationResultsResponse,
  EvaluationStatusResponse,
  EvaluationListResponse,
  EvaluationSubmitRequest,
  CriterionFeedbackRequest,
  CriterionFeedbackResponse,
  DeskQueueListResponse,
  TargetAgent,
} from '../types';

export const evaluationApi = {
  submitEvaluation: async (
    payload: EvaluationSubmitRequest,
  ): Promise<EvaluationResponse> => {
    return requestJson<EvaluationResponse>('/evaluations/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

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

  getDeskQueue: async (
    targetAgent: TargetAgent,
    program?: string,
  ): Promise<DeskQueueListResponse> => {
    const params = new URLSearchParams({ target_agent: targetAgent });
    if (program) {
      params.set('program', program);
     }
    return requestJson<DeskQueueListResponse>(`/evaluations/desk-queue?${params.toString()}`);
  },
};
