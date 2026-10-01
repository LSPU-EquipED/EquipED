// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest';
import { act, cleanup, renderHook } from '@testing-library/react';
import { useTrainingTablePagination } from '../useTrainingTablePagination';

afterEach(cleanup);

it('clamps the page after records shrink without reviving the old page on refresh', () => {
  const { result, rerender } = renderHook(({ items }) => useTrainingTablePagination(items, 'sme'), {
    initialProps: { items: Array.from({ length: 12 }, (_, index) => index) },
  });
  act(() => result.current.pagination.onPageChange(3));
  rerender({ items: [0, 1, 2, 3, 4, 5] });
  expect(result.current.pagination.page).toBe(2);
  expect(result.current.visibleItems).toEqual([5]);
  rerender({ items: [] });
  expect(result.current.pagination.page).toBe(1);
  expect(result.current.visibleItems).toEqual([]);
  rerender({ items: Array.from({ length: 12 }, (_, index) => index) });
  expect(result.current.pagination.page).toBe(1);
});

it('resets the page and row count when switching specialists', () => {
  const items = Array.from({ length: 25 }, (_, index) => index);
  const { result, rerender } = renderHook(
    ({ agentId }) => useTrainingTablePagination(items, agentId),
    { initialProps: { agentId: 'sme' } },
  );
  act(() => result.current.pagination.onPageSizeChange(10));
  act(() => result.current.pagination.onPageChange(2));
  rerender({ agentId: 'gad' });
  expect(result.current.pagination.page).toBe(1);
  expect(result.current.pagination.pageSize).toBe(5);
});
