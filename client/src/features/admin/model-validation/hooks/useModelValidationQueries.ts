import { useQuery } from '@tanstack/react-query';
import { modelValidationApi } from '../api/modelValidation.api';
import { terminalStatuses } from '../utils/helpers';

export function useModelValidationHistory() {
  return useQuery({
    queryKey: ['admin', 'model-validations'],
    queryFn: modelValidationApi.getModelValidations,
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => !terminalStatuses.has(item.status)) ? 3000 : false,
  });
}

export function useModelValidationCriteria() {
  return useQuery({
    queryKey: ['admin', 'model-validation-criteria'],
    queryFn: modelValidationApi.getModelValidationCriteria,
  });
}

export function useModelValidationMetrics(hasActiveValidations: boolean) {
  return useQuery({
    queryKey: ['admin', 'model-validation-metrics'],
    queryFn: modelValidationApi.getModelValidationMetrics,
    refetchInterval: hasActiveValidations ? 3000 : false,
  });
}

export function useModelValidationDetail(validationId: string, isExpanded: boolean) {
  return useQuery({
    queryKey: ['admin', 'model-validation', validationId],
    queryFn: () => modelValidationApi.getModelValidation(validationId),
    enabled: isExpanded,
    staleTime: 60_000,
  });
}

export function useModelValidationEvaluation(validationId: string, isExpanded: boolean) {
  return useQuery({
    queryKey: ['admin', 'model-validation-evaluation', validationId],
    queryFn: () => modelValidationApi.getModelValidationEvaluation(validationId),
    enabled: isExpanded,
    staleTime: 60_000,
  });
}
