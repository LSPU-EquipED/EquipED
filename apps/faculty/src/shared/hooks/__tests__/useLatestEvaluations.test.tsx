// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { evaluationsApi } from '@/shared/api/evaluations.api';
import { isEvaluationStatusActive, useLatestEvaluations } from '../useLatestEvaluations';

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('isEvaluationStatusActive', () => {
  it('returns true for active lifecycle statuses', () => {
    expect(isEvaluationStatusActive('SUBMITTED')).toBe(true);
    expect(isEvaluationStatusActive('PREPROCESSING')).toBe(true);
    expect(isEvaluationStatusActive('EVALUATING')).toBe(true);
    expect(isEvaluationStatusActive('SYNTHESIZING')).toBe(true);
    expect(isEvaluationStatusActive('PENDING')).toBe(true);
    expect(isEvaluationStatusActive('PROCESSING')).toBe(true);
  });

  it('returns false for terminal or empty statuses', () => {
    expect(isEvaluationStatusActive('COMPLETED')).toBe(false);
    expect(isEvaluationStatusActive('COMPLETED_PARTIAL')).toBe(false);
    expect(isEvaluationStatusActive('FAILED')).toBe(false);
    expect(isEvaluationStatusActive(null)).toBe(false);
    expect(isEvaluationStatusActive(undefined)).toBe(false);
  });
});

describe('useLatestEvaluations hook', () => {
  it('is disabled and returns empty mapping when documentIds is empty', () => {
    const spy = vi.spyOn(evaluationsApi, 'getLatestEvaluations');
    const { result } = renderHook(() => useLatestEvaluations([]), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(result.current.latestEvalsByDocId).toEqual({});
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it('fetches latest evaluations and maps them by document_id', async () => {
    const mockItems = [
      {
        document_id: 'doc-1',
        evaluation_id: 'eval-1',
        status: 'COMPLETED',
        submitted_at: '2026-08-20T10:00:00Z',
      },
      {
        document_id: 'doc-2',
        evaluation_id: 'eval-2',
        status: 'EVALUATING',
        submitted_at: '2026-08-21T10:00:00Z',
      },
    ];
    const spy = vi.spyOn(evaluationsApi, 'getLatestEvaluations').mockResolvedValueOnce({
      items: mockItems,
    });

    const { result } = renderHook(() => useLatestEvaluations(['doc-2', 'doc-1']), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.latestEvalsByDocId['doc-1']?.status).toBe('COMPLETED');
    expect(result.current.latestEvalsByDocId['doc-2']?.status).toBe('EVALUATING');
    expect(result.current.hasActiveEvaluations).toBe(true);

    spy.mockRestore();
  });

  it('collapses repeated evaluation records to the latest state per SLM', async () => {
    const mockItems = [
      {
        document_id: 'doc-1',
        evaluation_id: 'eval-old',
        status: 'FAILED',
        submitted_at: '2026-08-19T08:00:00Z',
      },
      {
        document_id: 'doc-1',
        evaluation_id: 'eval-new',
        status: 'COMPLETED',
        submitted_at: '2026-08-20T10:00:00Z',
      },
    ];
    const spy = vi.spyOn(evaluationsApi, 'getLatestEvaluations').mockResolvedValueOnce({
      items: mockItems,
    });

    const { result } = renderHook(() => useLatestEvaluations(['doc-1']), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Must resolve to eval-new (latest timestamp)
    expect(result.current.latestEvalsByDocId['doc-1']?.evaluation_id).toBe('eval-new');
    expect(result.current.latestEvalsByDocId['doc-1']?.status).toBe('COMPLETED');

    spy.mockRestore();
  });
});
