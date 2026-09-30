import { useState } from 'react';
import { usePreferenceLogs } from './usePreferenceLogs';

export function usePreferenceLogTable() {
  const [actionFilter, setActionFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [expandedLogIds, setExpandedLogIds] = useState<Set<string>>(new Set());

  const { data, isLoading, isError } = usePreferenceLogs({
    action: actionFilter !== 'all' ? actionFilter : undefined,
    page,
    page_size: pageSize,
  });

  function changeActionFilter(filterId: string) {
    setActionFilter(filterId);
    setPage(1);
  }

  function changePageSize(newPageSize: number) {
    setPageSize(newPageSize);
    setPage(1);
  }

  function toggleExpand(logId: string) {
    setExpandedLogIds((previous) => {
      const next = new Set(previous);
      if (next.has(logId)) next.delete(logId);
      else next.add(logId);
      return next;
    });
  }

  const logs = data?.items ?? [];
  const totalRecords = data?.total ?? logs.length;

  return {
    logs,
    isLoading,
    isError,
    actionFilter,
    page,
    pageSize,
    expandedLogIds,
    totalRecords,
    showPagination:
      !isLoading && !isError && logs.length > 0 && totalRecords > 0,
    changeActionFilter,
    changePageSize,
    changePage: setPage,
    toggleExpand,
  };
}
