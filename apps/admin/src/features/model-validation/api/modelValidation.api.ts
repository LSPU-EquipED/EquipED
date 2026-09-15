import { requestJson } from '@/shared/api/http';
import type {
  AdminEvaluationResponse,
  ModelValidationCreateBody,
  ModelValidationCriteriaResponse,
  ModelValidationItem,
  ModelValidationListResponse,
  ModelValidationMetricsResponse,
} from '../types';

export const modelValidationApi = {
  createModelValidation: (body: ModelValidationCreateBody) =>
    requestJson<ModelValidationItem>('/admin/model-validations', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getModelValidations: () => requestJson<ModelValidationListResponse>('/admin/model-validations'),

  getModelValidation: (validationId: string) =>
    requestJson<ModelValidationItem>(`/admin/model-validations/${validationId}`),

  getModelValidationEvaluation: (validationId: string) =>
    requestJson<AdminEvaluationResponse>(`/admin/model-validations/${validationId}/evaluation`),

  getModelValidationMetrics: () =>
    requestJson<ModelValidationMetricsResponse>('/admin/model-validations/metrics'),

  getModelValidationCriteria: () =>
    requestJson<ModelValidationCriteriaResponse>('/admin/model-validations/criteria'),
};
