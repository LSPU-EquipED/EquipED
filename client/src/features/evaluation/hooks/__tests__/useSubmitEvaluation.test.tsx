// @vitest-environment jsdom
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSubmitEvaluation } from '../useSubmitEvaluation';
import { evaluationApi } from '../../api/evaluation.api';
import type { EvaluationResponse } from '../../types';

vi.mock('../../api/evaluation.api', () => ({
  evaluationApi: {
    submitEvaluation: vi.fn(),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  return { wrapper, queryClient };
}

describe('useSubmitEvaluation', () => {
  beforeEach(() => {
    vi.mocked(evaluationApi.submitEvaluation).mockReset();
  });

  it('successfully submits full evaluation payload and sets query cache', async () => {
    const { wrapper, queryClient } = createWrapper();
    const mockResponse: EvaluationResponse = {
      evaluation_id: 'eval-full-1',
      document_id: 'doc-100',
      curriculum_id: 'curr-100',
      status: 'SUBMITTED',
      partial_without_curriculum: false,
      submitted_at: '2026-08-24T10:00:00Z',
    };

    vi.mocked(evaluationApi.submitEvaluation).mockResolvedValueOnce(mockResponse);

    const { result } = renderHook(() => useSubmitEvaluation(), { wrapper });

    result.current.mutate({
      document_id: 'doc-100',
      curriculum_id: 'curr-100',
      confirmed_program: 'BSCS',
      partial_without_curriculum: false,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(evaluationApi.submitEvaluation).toHaveBeenCalledWith({
      document_id: 'doc-100',
      curriculum_id: 'curr-100',
      confirmed_program: 'BSCS',
      partial_without_curriculum: false,
    });

    expect(queryClient.getQueryData(['resolve-evaluation', 'doc-100'])).toBe('eval-full-1');
    expect(queryClient.getQueryData(['evaluation-status', 'eval-full-1'])).toEqual({
      evaluation_id: 'eval-full-1',
      status: 'SUBMITTED',
      error_message: undefined,
      partial_without_curriculum: false,
      partial_reason: undefined,
      completed_at: undefined,
      duration_seconds: undefined,
    });
  });

  it('successfully submits partial evaluation payload', async () => {
    const { wrapper } = createWrapper();
    const mockResponse: EvaluationResponse = {
      evaluation_id: 'eval-partial-1',
      document_id: 'doc-200',
      status: 'SUBMITTED',
      partial_without_curriculum: true,
      submitted_at: '2026-08-24T11:00:00Z',
    };

    vi.mocked(evaluationApi.submitEvaluation).mockResolvedValueOnce(mockResponse);

    const { result } = renderHook(() => useSubmitEvaluation(), { wrapper });

    result.current.mutate({
      document_id: 'doc-200',
      confirmed_program: 'BSInfoTech',
      partial_without_curriculum: true,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(evaluationApi.submitEvaluation).toHaveBeenCalledWith({
      document_id: 'doc-200',
      confirmed_program: 'BSInfoTech',
      partial_without_curriculum: true,
    });
  });
});
