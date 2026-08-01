import { requestJson } from '@/shared/api/http';
import type {
  EvaluationResponse,
  EvaluationResultsResponse,
  EvaluationStatusResponse,
  EvaluationListResponse,
  SyllabusOutcomesResponse,
  SyllabusAlignmentStartResponse,
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

  getSyllabusOutcomes: async (id: string): Promise<SyllabusOutcomesResponse> => {
    return requestJson<SyllabusOutcomesResponse>(`/documents/${id}/outcomes`);
  },

  startSmeSyllabusAlignment: async (
    evaluationId: string,
  ): Promise<SyllabusAlignmentStartResponse> => {
    return requestJson<SyllabusAlignmentStartResponse>(
      `/evaluations/${evaluationId}/sme-syllabus-alignment`,
      { method: 'POST' },
    );
  },
};
