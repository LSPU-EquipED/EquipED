import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage, isApiError } from '@/shared/api/http';
import { rubricEditorApi } from '../api/rubricEditor.api';
import type {
  CriterionUpdate,
  DomainTitleUpdate,
  RubricCriterionCreate,
  RubricCriterionMoveRequest,
  RubricCriterionUpdate,
  RubricDomainCreate,
  RubricDomainUpdate,
  RubricReorderRequest,
  ValidationIssue,
  ValidationReport,
} from '../types';

export const RUBRICS_QUERY_KEY = ['adminRubrics'];

export function useRubricSets(params?: { all_revisions?: boolean; agent_id?: string }) {
  return useQuery({
    queryKey: [...RUBRICS_QUERY_KEY, 'list', params],
    queryFn: () => rubricEditorApi.getRubricSets(params),
  });
}

export function useRubricRevisions(agentId?: string) {
  return useQuery({
    queryKey: [...RUBRICS_QUERY_KEY, 'revisions', agentId ?? 'all'],
    queryFn: () => rubricEditorApi.getRevisions(agentId),
  });
}

export function useRubricSet(rubricSetId?: string | null) {
  return useQuery({
    queryKey: [...RUBRICS_QUERY_KEY, 'set', rubricSetId],
    queryFn: () => rubricEditorApi.getRubricSetById(rubricSetId!),
    enabled: Boolean(rubricSetId),
  });
}

export function useCreateDraft() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (agentId: string) => rubricEditorApi.createDraft(agentId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useDeleteDraft() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (rubricSetId: string) => rubricEditorApi.deleteDraft(rubricSetId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useValidateDraft() {
  return useMutation({
    mutationFn: (rubricSetId: string) => rubricEditorApi.validateDraft(rubricSetId),
  });
}

export function usePublishRevision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ rubricSetId, activate = true }: { rubricSetId: string; activate?: boolean }) =>
      rubricEditorApi.publishRevision(rubricSetId, activate),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useActivateRevision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (rubricSetId: string) => rubricEditorApi.activateRevision(rubricSetId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useRetireRevision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (rubricSetId: string) => rubricEditorApi.retireRevision(rubricSetId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useReorderRubricTree() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ rubricSetId, body }: { rubricSetId: string; body: RubricReorderRequest }) =>
      rubricEditorApi.reorderRubricTree(rubricSetId, body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useCreateDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ rubricSetId, body }: { rubricSetId: string; body: RubricDomainCreate }) =>
      rubricEditorApi.createDomain(rubricSetId, body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useUpdateDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      domainId,
      body,
    }: {
      domainId: string;
      body: RubricDomainUpdate | DomainTitleUpdate;
    }) => rubricEditorApi.updateDomain(domainId, body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useDeleteDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (domainId: string) => rubricEditorApi.deleteDomain(domainId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useCreateCriterion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ domainId, body }: { domainId: string; body: RubricCriterionCreate }) =>
      rubricEditorApi.createCriterion(domainId, body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useUpdateCriterion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      criterionId,
      body,
    }: {
      criterionId: string;
      body: RubricCriterionUpdate | CriterionUpdate;
    }) => rubricEditorApi.updateCriterion(criterionId, body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useMoveCriterion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      criterionId,
      body,
    }: {
      criterionId: string;
      body: RubricCriterionMoveRequest;
    }) => rubricEditorApi.moveCriterion(criterionId, body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function useDeleteCriterion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (criterionId: string) => rubricEditorApi.deleteCriterion(criterionId),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: RUBRICS_QUERY_KEY });
    },
  });
}

export function getRubricOperationError(
  error: unknown,
  fallback = 'Could not save rubric change. Please try again.',
): string {
  if (isApiError(error)) {
    if (error.status === 409) {
      return (
        error.detail || 'The requested action conflicts with the current form or revision state.'
      );
    }
    if (error.status === 422) {
      const report = getValidationReportFromError(error);
      if (report && report.issues.length > 0) {
        return `Validation failed with ${report.issues.length} issue(s): ${report.issues.map((i) => i.message).join('; ')}`;
      }
      return error.detail || 'Submitted form data is invalid.';
    }
    return error.detail || error.message;
  }
  return getErrorMessage(error, fallback);
}

export function getValidationReportFromError(error: unknown): ValidationReport | null {
  if (
    isApiError(error) &&
    error.status === 422 &&
    typeof error.payload === 'object' &&
    error.payload !== null
  ) {
    const payload = error.payload as {
      detail?: {
        is_valid?: boolean;
        issues?: ValidationIssue[];
        estimated_prompt_chars?: number;
        criteria_count?: number;
      };
    };
    if (
      payload.detail &&
      typeof payload.detail === 'object' &&
      Array.isArray(payload.detail.issues)
    ) {
      return {
        is_valid: Boolean(payload.detail.is_valid),
        issues: payload.detail.issues,
        estimated_prompt_chars: Number(payload.detail.estimated_prompt_chars ?? 0),
        criteria_count: Number(payload.detail.criteria_count ?? 0),
      };
    }
  }
  return null;
}

export function isConflictError(error: unknown): boolean {
  return isApiError(error) && error.status === 409;
}
