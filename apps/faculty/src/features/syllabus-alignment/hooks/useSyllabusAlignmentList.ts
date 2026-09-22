import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { alignmentApi } from '../api/syllabusAlignment.api';
import {
  deriveSyllabusMetrics,
  type StatusFilter,
} from '../utils/syllabusFiltering';

export function useSyllabusAlignmentList(pageSize = 10) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');

  const handleSearchChange = (val: string) => {
    setSearch(val);
    setPage(1);
  };

  const handleStatusFilterChange = (filter: StatusFilter) => {
    setStatusFilter(filter);
    setPage(1);
  };

  const slms = useQuery({
    queryKey: ['syllabus-alignment-slms', page, pageSize, search, statusFilter],
    queryFn: () =>
      alignmentApi.listSlms(page, pageSize, {
        search: search.trim() ? search.trim() : undefined,
        status_filter: statusFilter !== 'ALL' ? statusFilter : undefined,
      }),
    refetchInterval: (query) =>
      (query.state.data?.items ?? []).some((item) =>
        ['QUEUED', 'RUNNING'].includes(item.current_result?.status ?? ''),
      )
        ? 3000
        : false,
  });

  const stats = slms.data?.stats;
  const total = slms.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const rawItems = slms.data?.items ?? [];

  const metrics = useMemo(() => {
    return deriveSyllabusMetrics(stats, rawItems);
  }, [stats, rawItems]);

  const filteredItems = rawItems;

  return {
    page,
    setPage,
    search,
    setSearch,
    handleSearchChange,
    statusFilter,
    setStatusFilter,
    handleStatusFilterChange,
    slms,
    stats,
    total,
    totalPages,
    items: rawItems,
    metrics,
    filteredItems,
  };
}
