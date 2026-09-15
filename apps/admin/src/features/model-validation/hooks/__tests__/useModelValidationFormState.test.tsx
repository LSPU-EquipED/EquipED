// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useModelValidationFormState } from '../useModelValidationFormState';
import { modelValidationApi } from '../../api/modelValidation.api';
import { documentsApi } from '@/shared/api/documents.api';
import { ApiError } from '@/shared/api/http';
import type { ClientDocument } from '@/shared/types/documents';
import type {
  ModelValidationCreateBody,
  ModelValidationCriteriaResponse,
  ModelValidationItem,
} from '../../types';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const mockReadyDoc: ClientDocument = {
  documentId: 'doc-ready-1',
  title: 'SLM 1',
  sourceType: 'slm',
  processingStatus: 'PROCESSED',
  academicYear: null,
  courseCode: null,
  courseTitle: null,
  lessonTitle: null,
  program: null,
  pageCount: 1,
  hasOcrPages: false,
  uploadedAt: '2026-08-30T00:00:00Z',
  chunks: [
    {
      chunkId: 'c-1',
      documentId: 'doc-ready-1',
      sourceType: 'slm',
      agentDomain: 'sme',
      pageNumber: 1,
      text: 'Text chunk 1',
      tokenCount: 10,
      isOcr: false,
    },
  ],
};

const mockCriteriaCatalog: ModelValidationCriteriaResponse = {
  agents: [
    {
      agent_id: 'sme',
      agent_name: 'Subject Matter Expert',
      rubric_set_id: 'set-sme-123',
      rubric_version: 1,
      domains: [
        {
          rubric_domain_id: 'dom-sme-1',
          code: 'CONTENT',
          title: 'Content Quality',
          display_order: 1,
          criteria: [
            {
              rubric_criterion_id: 'crit-sme-1',
              criterion_code: 'SME_1',
              criterion_id: 'crit-sme-1',
              title: 'Accuracy',
              description: 'Check content accuracy',
              display_order: 1,
            },
          ],
        },
      ],
      criteria: [
        {
          rubric_criterion_id: 'crit-sme-1',
          criterion_code: 'SME_1',
          criterion_id: 'crit-sme-1',
          title: 'Accuracy',
          description: 'Check content accuracy',
          display_order: 1,
        },
      ],
    },
    {
      agent_id: 'coordinator',
      agent_name: 'Program Coordinator',
      rubric_set_id: 'set-coord-123',
      rubric_version: 1,
      domains: [],
      criteria: [
        {
          rubric_criterion_id: 'crit-coord-1',
          criterion_code: 'COORD_1',
          criterion_id: 'crit-coord-1',
          title: 'Curriculum Alignment',
          description: 'Check curriculum alignment',
          display_order: 1,
        },
      ],
    },
    {
      agent_id: 'gad',
      agent_name: 'GAD',
      rubric_set_id: 'set-gad-123',
      rubric_version: 2,
      domains: [],
      criteria: [
        {
          rubric_criterion_id: 'crit-gad-1',
          criterion_code: 'GAD_1',
          criterion_id: 'crit-gad-1',
          title: 'Inclusivity',
          description: 'Check gender sensitivity',
          display_order: 1,
        },
      ],
    },
    {
      agent_id: 'itso',
      agent_name: 'ITSO',
      rubric_set_id: 'set-itso-123',
      rubric_version: 1,
      domains: [],
      criteria: [
        {
          rubric_criterion_id: 'crit-itso-1',
          criterion_code: 'ITSO_1',
          criterion_id: 'crit-itso-1',
          title: 'Data Security',
          description: 'Check data privacy',
          display_order: 1,
        },
      ],
    },
  ],
  total_criteria: 4,
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useModelValidationFormState', () => {
  it('filters criteria catalog down to SME, GAD, and ITSO only, omitting Coordinator in partial workflow', async () => {
    vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue(
      mockCriteriaCatalog,
    );

    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.criterionDefinitions.length).toBe(3);
    });

    const agentIds = result.current.criterionDefinitions.map((a) => a.agent_id);
    expect(agentIds).toEqual(['sme', 'gad', 'itso']);
    expect(agentIds).not.toContain('coordinator');
  });

  it('submits every expected score as exact {agent_id, rubric_set_id, rubric_criterion_id, expected_score}', async () => {
    vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue(
      mockCriteriaCatalog,
    );
    vi.spyOn(documentsApi, 'uploadDocument').mockResolvedValue({
      documentId: 'doc-ready-1',
      title: 'SLM 1',
      sourceType: 'slm',
      processingStatus: 'PROCESSED',
      academicYear: null,
      courseCode: null,
      courseTitle: null,
      lessonTitle: null,
    });
    vi.spyOn(documentsApi, 'getDocument').mockResolvedValue(mockReadyDoc);

    let submittedBody: ModelValidationCreateBody | undefined;
    vi.spyOn(modelValidationApi, 'createModelValidation').mockImplementation(async (body) => {
      submittedBody = body;
      const createdItem: ModelValidationItem = {
        validation_id: 'val-1',
        evaluation_id: 'eval-1',
        document_id: body.document_id,
        document_title: 'SLM 1',
        partial_without_curriculum: true,
        bound_forms: [],
        criterion_scores: [],
        absolute_error: null,
        latency_seconds: null,
        score_perplexity: null,
        toxicity_score: null,
        toxicity_label: null,
        toxicity_explanation: null,
        toxicity_model: null,
        toxicity_error: null,
        status: 'SUBMITTED',
        error_message: null,
        created_at: '2026-08-30T00:00:00Z',
      };
      return createdItem;
    });

    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.criterionDefinitions.length).toBe(3);
    });

    // Upload document
    await act(async () => {
      result.current.uploadMutation.mutate({
        file: new File(['dummy'], 'slm.pdf', { type: 'application/pdf' }),
        title: 'SLM 1',
        program: 'BSCS',
      });
    });

    await waitFor(() => {
      expect(result.current.uploaded).not.toBeNull();
      expect(result.current.uploadedDocumentReady).toBe(true);
    });

    // Enter all scores and acknowledge partial
    act(() => {
      result.current.setExpectedScores({
        'sme:crit-sme-1': '4',
        'gad:crit-gad-1': '3',
        'itso:crit-itso-1': '4',
      });
      result.current.setPartialChoiceAcknowledged(true);
    });

    expect(result.current.allCriterionScoresComplete).toBe(true);
    expect(result.current.canSubmitEvaluation).toBe(true);

    await act(async () => {
      result.current.handleStart();
    });

    expect(submittedBody).not.toBeNull();
    expect(submittedBody?.document_id).toBe('doc-ready-1');
    expect(submittedBody?.partial_without_curriculum).toBe(true);
    expect(submittedBody?.expected_scores).toEqual([
      {
        agent_id: 'sme',
        rubric_set_id: 'set-sme-123',
        rubric_criterion_id: 'crit-sme-1',
        expected_score: 4,
      },
      {
        agent_id: 'gad',
        rubric_set_id: 'set-gad-123',
        rubric_criterion_id: 'crit-gad-1',
        expected_score: 3,
      },
      {
        agent_id: 'itso',
        rubric_set_id: 'set-itso-123',
        rubric_criterion_id: 'crit-itso-1',
        expected_score: 4,
      },
    ]);
  });

  it('detects stale 409/422 errors and allows catalog reload', async () => {
    vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue(
      mockCriteriaCatalog,
    );
    vi.spyOn(documentsApi, 'uploadDocument').mockResolvedValue({
      documentId: 'doc-ready-1',
      title: 'SLM 1',
      sourceType: 'slm',
      processingStatus: 'PROCESSED',
      academicYear: null,
      courseCode: null,
      courseTitle: null,
      lessonTitle: null,
    });
    vi.spyOn(documentsApi, 'getDocument').mockResolvedValue(mockReadyDoc);

    const apiError = new ApiError('Conflict: rubric revision changed', {
      status: 409,
      payload: { detail: 'Rubric revision updated' },
    });
    vi.spyOn(modelValidationApi, 'createModelValidation').mockRejectedValue(apiError);

    const { result } = renderHook(() => useModelValidationFormState(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.criterionDefinitions.length).toBe(3);
    });

    await act(async () => {
      result.current.uploadMutation.mutate({
        file: new File(['dummy'], 'slm.pdf', { type: 'application/pdf' }),
        title: 'SLM 1',
        program: 'BSCS',
      });
    });

    await waitFor(() => {
      expect(result.current.uploadedDocumentReady).toBe(true);
    });

    act(() => {
      result.current.setExpectedScores({
        'sme:crit-sme-1': '4',
        'gad:crit-gad-1': '3',
        'itso:crit-itso-1': '4',
      });
      result.current.setPartialChoiceAcknowledged(true);
    });

    await act(async () => {
      result.current.handleStart();
    });

    await waitFor(() => {
      expect(result.current.isStaleBinding).toBe(true);
    });

    const refetchSpy = vi.spyOn(result.current.criterionCatalog, 'refetch');
    await act(async () => {
      await result.current.handleReloadCatalog();
    });

    expect(refetchSpy).toHaveBeenCalled();
  });
});
