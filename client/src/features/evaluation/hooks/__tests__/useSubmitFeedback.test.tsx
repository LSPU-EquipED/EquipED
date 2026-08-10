// @vitest-environment jsdom
//
// This hook wraps @tanstack/react-query's useMutation, which requires a
// real render tree (it reads/writes state via React's hook dispatcher).
// The rest of this project's tests run under `environment: 'node'` (see
// vitest.config.ts) because they exercise pure functions or call
// non-hook component functions directly. Hook tests need a DOM, so this
// file opts into jsdom locally via the pragma above instead of changing
// the global config.
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useSubmitCriterionFeedback } from '../useSubmitFeedback';
import { evaluationApi } from '../../api/evaluation.api';

vi.mock('../../api/evaluation.api', () => ({
  evaluationApi: {
    submitCriterionFeedback: vi.fn(),
  },
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient();
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useSubmitCriterionFeedback', () => {
  beforeEach(() => {
    vi.mocked(evaluationApi.submitCriterionFeedback).mockReset();
  });

  it('calls submitCriterionFeedback with the evaluation id, criterion id, and body', async () => {
    vi.mocked(evaluationApi.submitCriterionFeedback).mockResolvedValue({
      log_id: '1',
      evaluation_id: 'eval-1',
      user_id: 'user-1',
      agent_name: 'itso',
      criterion_id: 'itso-03',
      action: 'ACCEPT',
      edited_json: null,
      notes: null,
      created_at: '2026-08-10T00:00:00Z',
    });

    const { result } = renderHook(() => useSubmitCriterionFeedback('eval-1'), { wrapper });

    result.current.mutate({
      criterionId: 'itso-03',
      body: { agent_name: 'itso', action: 'ACCEPT' },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(evaluationApi.submitCriterionFeedback).toHaveBeenCalledWith(
      'eval-1',
      'itso-03',
      { agent_name: 'itso', action: 'ACCEPT' },
    );
  });
});
