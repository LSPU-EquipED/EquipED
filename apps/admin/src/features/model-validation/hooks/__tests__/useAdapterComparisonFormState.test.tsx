// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useAdapterComparisonFormState } from '../useAdapterComparisonFormState';
import { modelValidationApi } from '../../api/modelValidation.api';
import { documentsApi } from '@equiped/api-client';
import type { ClientDocument } from '@equiped/types';
import type { AdapterComparisonCreateBody, ModelValidationCriteriaResponse } from '../../types';

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
      domains: [],
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
  ],
  total_criteria: 2,
};

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useAdapterComparisonFormState', () => {
  it('lists SME, GAD, and ITSO as compare-eligible agents, omitting Coordinator', async () => {
    vi.spyOn(modelValidationApi, 'getModelValidationCriteria').mockResolvedValue(
      mockCriteriaCatalog,
    );

    const { result } = renderHook(() => useAdapterComparisonFormState(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.compareAgents.length).toBe(2);
    });

    const agentIds = result.current.compareAgents.map((a) => a.agent_id);
    expect(agentIds).toEqual(['sme', 'gad']);
    expect(agentIds).not.toContain('coordinator');
  });

  it('is not submittable until an agent is selected and all its criteria are scored', async () => {
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

    const { result } = renderHook(() => useAdapterComparisonFormState(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.compareAgents.length).toBe(2);
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

    expect(result.current.canSubmitEvaluation).toBe(false);

    act(() => {
      result.current.setSelectedAgent('sme');
    });
    expect(result.current.canSubmitEvaluation).toBe(false);

    act(() => {
      result.current.setExpectedScores({ 'sme:crit-sme-1': '3' });
    });
    expect(result.current.canSubmitEvaluation).toBe(true);
  });

  it('submits with target_agent set to the selected agent and only that agent\'s expected_scores', async () => {
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

    let submittedBody: AdapterComparisonCreateBody | undefined;
    vi.spyOn(modelValidationApi, 'compareAdapter').mockImplementation(async (body) => {
      submittedBody = body;
      return { compare_group_id: 'group-1', base_validation_id: 'v-base', adapter_validation_id: 'v-adapter' };
    });

    const { result } = renderHook(() => useAdapterComparisonFormState(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.compareAgents.length).toBe(2);
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
      result.current.setSelectedAgent('sme');
      result.current.setExpectedScores({ 'sme:crit-sme-1': '3' });
    });

    expect(result.current.canSubmitEvaluation).toBe(true);

    await act(async () => {
      result.current.handleStart();
    });

    expect(submittedBody).not.toBeUndefined();
    expect(submittedBody?.document_id).toBe('doc-ready-1');
    expect(submittedBody?.target_agent).toBe('sme');
    expect(submittedBody?.expected_scores).toEqual([
      { agent_id: 'sme', rubric_set_id: 'set-sme-123', rubric_criterion_id: 'crit-sme-1', expected_score: 3 },
    ]);
  });
});
