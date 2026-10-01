import { useState } from 'react';
import type { TrainingTablePaginationControls } from '../types';

const DEFAULT_PAGE_SIZE = 5;

export function useTrainingTablePagination<T>(
  items: T[],
  agentId: string,
): { visibleItems: T[]; pagination: TrainingTablePaginationControls } {
  const [selection, setSelection] = useState({ agentId, page: 1, pageSize: DEFAULT_PAGE_SIZE });
  const current =
    selection.agentId === agentId ? selection : { agentId, page: 1, pageSize: DEFAULT_PAGE_SIZE };
  const totalPages = Math.max(1, Math.ceil(items.length / current.pageSize));
  const page = Math.min(current.page, totalPages);

  // Reset for a different specialist and keep the last available page after a list shrinks.
  if (selection.agentId !== agentId || selection.page !== page) {
    setSelection({ ...current, page });
  }

  return {
    visibleItems: items.slice((page - 1) * current.pageSize, page * current.pageSize),
    pagination: {
      page,
      pageSize: current.pageSize,
      totalPages,
      totalRecords: items.length,
      showPagination: items.length > DEFAULT_PAGE_SIZE,
      onPageChange: (nextPage: number) =>
        setSelection({ ...current, page: Math.max(1, Math.min(nextPage, totalPages)) }),
      onPageSizeChange: (pageSize: number) => setSelection({ agentId, page: 1, pageSize }),
    },
  };
}
