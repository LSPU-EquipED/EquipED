// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { ModelValidationItem } from '../../types';
import { useValidationHistoryState } from '../useValidationHistoryState';

afterEach(cleanup);

const items: ModelValidationItem[] = Array.from({ length: 25 }, (_, index) => ({
  validation_id: `run-${index}`,
  evaluation_id: `evaluation-${index}`,
  document_id: `document-${index}`,
  document_title: index === 0 ? null : `Module ${index}`,
  model_variant: index % 2 === 0 ? 'base' : 'adapter',
  adapter_id: null,
  adapter_label: null,
  adapter_resolution: null,
  compare_group_id: null,
  partial_without_curriculum: false,
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
  status: index % 3 === 0 ? 'FAILED' : 'COMPLETED',
  error_message: null,
  created_at: '2026-09-01T00:00:00Z',
}));

describe('useValidationHistoryState', () => {
  it('combines case-insensitive search, status, and model filters and resets pagination', () => {
    const { result } = renderHook(() => useValidationHistoryState(items));
    act(() => result.current.setPage(3));
    expect(result.current.paginatedItems).toHaveLength(5);

    act(() => {
      result.current.setSearchTerm('  MODULE 1 ');
      result.current.setStatusFilter('COMPLETED');
      result.current.setModelFilter('adapter');
    });
    expect(result.current.currentPage).toBe(1);
    expect(result.current.paginatedItems.map((item) => item.validation_id)).toEqual([
      'run-1',
      'run-11',
      'run-13',
      'run-17',
      'run-19',
    ]);

    act(() => result.current.resetFilters());
    expect(result.current.hasActiveFilters).toBe(false);
    expect(result.current.totalRecords).toBe(25);

    act(() => result.current.setSearchTerm('RUN-0'));
    expect(result.current.paginatedItems).toEqual([items[0]]);
  });

  it('resets the page size and clamps the current page when refreshed results shrink', () => {
    const { result, rerender } = renderHook(({ runs }) => useValidationHistoryState(runs), {
      initialProps: { runs: items },
    });
    act(() => result.current.setPage(3));
    expect([result.current.startRecord, result.current.endRecord]).toEqual([21, 25]);

    act(() => result.current.setPageSize(20));
    expect(result.current.currentPage).toBe(1);
    expect(result.current.paginatedItems).toHaveLength(20);

    act(() => result.current.setPage(2));
    rerender({ runs: items.slice(0, 3) });
    expect(result.current.currentPage).toBe(1);
    expect([result.current.startRecord, result.current.endRecord]).toEqual([1, 3]);

    rerender({ runs: [] });
    expect(result.current.paginatedItems).toEqual([]);
    expect(result.current.totalPages).toBe(1);
    expect([result.current.startRecord, result.current.endRecord]).toEqual([0, 0]);
  });

  it('keeps the selected review available while filtering and closes it with Escape', () => {
    const { result } = renderHook(() => useValidationHistoryState(items));
    act(() => result.current.setExpandedValidationId('run-1'));
    act(() => result.current.setSearchTerm('no matching document'));
    expect(result.current.paginatedItems).toEqual([]);
    expect(result.current.selectedItem).toBe(items[1]);

    act(() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })));
    expect(result.current.selectedItem).toBeNull();
  });
});
