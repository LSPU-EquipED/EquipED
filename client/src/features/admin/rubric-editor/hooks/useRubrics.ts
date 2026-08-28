import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getErrorMessage } from '@/shared/api/http';
import { rubricEditorApi } from '../api/rubricEditor.api';
import type { CriterionTextUpdate, DomainTitleUpdate } from '../types';

const QUERY_KEY = ['adminRubrics'];

export function useRubricSets() {
  return useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => rubricEditorApi.getRubricSets(),
  });
}

export function useUpdateCriterion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ criterionId, body }: { criterionId: string; body: CriterionTextUpdate }) =>
      rubricEditorApi.updateCriterion(criterionId, body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function useUpdateDomain() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ domainId, body }: { domainId: string; body: DomainTitleUpdate }) =>
      rubricEditorApi.updateDomain(domainId, body),
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function getRubricOperationError(error: unknown): string {
  return getErrorMessage(error, 'Could not save rubric change. Please try again.');
}
