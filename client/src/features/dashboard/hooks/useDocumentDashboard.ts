import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '@/features/dashboard/api/dashboard.api';
import type { ClientDocument } from '@/shared/types/documents';
import { sourceTypeLabels } from '../utils/document.utils';

export type StatusFilter = 'all' | 'PROCESSED' | 'PENDING' | 'FAILED';

const isProcessingStatus = (status: ClientDocument['processingStatus']) =>
  status === 'PENDING' || status === 'PROCESSING' || status === 'CLEANUP_PENDING';

export function useDocumentDashboard() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const handleSetSearch = (val: string) => {
    setSearch(val);
    setPage(1);
  };

  const handleSetStatusFilter = (val: StatusFilter) => {
    setStatusFilter(val);
    setPage(1);
  };

  const { data, error, isLoading } = useQuery({
    queryKey: ['documents', { sourceType: 'slm' }],
    queryFn: () => dashboardApi.listDocuments({ sourceType: 'slm' }),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((d: ClientDocument) => isProcessingStatus(d.processingStatus))
        ? 4000
        : false;
    },
  });

  const stats = useMemo(() => {
    const items = data?.items ?? [];
    return {
      total: items.length,
      ready: items.filter((d) => d.processingStatus === 'PROCESSED').length,
      processing: items.filter((d) => isProcessingStatus(d.processingStatus)).length,
      failed: items.filter((d) => d.processingStatus === 'FAILED').length,
    };
  }, [data?.items]);

  const documents = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    const items = data?.items ?? [];

    return items.filter((doc) => {
      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'PENDING'
          ? isProcessingStatus(doc.processingStatus)
          : doc.processingStatus === statusFilter);
      const matchesSearch =
        !normalizedSearch ||
        [doc.title, doc.program, doc.courseTitle, sourceTypeLabels[doc.sourceType]]
          .filter(Boolean)
          .some((val) => val?.toLowerCase().includes(normalizedSearch));
      return matchesStatus && matchesSearch;
    });
  }, [data?.items, search, statusFilter]);

  const totalPages = Math.ceil(documents.length / pageSize) || 1;

  const paginatedDocuments = useMemo(() => {
    const start = (page - 1) * pageSize;
    return documents.slice(start, start + pageSize);
  }, [documents, page, pageSize]);

  return {
    search,
    setSearch: handleSetSearch,
    statusFilter,
    setStatusFilter: handleSetStatusFilter,
    page,
    setPage,
    pageSize,
    setPageSize,
    stats,
    documents,
    paginatedDocuments,
    totalPages,
    error,
    isLoading,
    isTableReady: !isLoading || !!data,
    data,
  };
}
