import { useEffect, useMemo, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { documentsFeatureApi } from '../api/documents.api';
import type { DocumentApiStatus, ListDocumentsParams } from '@/shared/api/documents.api';

export type StatusFilter = 'all' | 'PROCESSED' | 'PROCESSING' | 'FAILED' | 'PENDING';

function mapStatusFilterToApi(filter: StatusFilter): DocumentApiStatus | undefined {
  switch (filter) {
    case 'PROCESSED':
      return 'ready';
    case 'PROCESSING':
    case 'PENDING':
      return 'processing';
    case 'FAILED':
      return 'failed';
    case 'all':
    default:
      return undefined;
  }
}

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

  const handleSetPageSize = (val: number) => {
    setPageSize(val);
    setPage(1);
  };

  const apiStatus = mapStatusFilterToApi(statusFilter);
  const trimmedSearch = search.trim();

  const queryParams: ListDocumentsParams = {
    sourceType: 'slm',
    page,
    pageSize,
    search: trimmedSearch || undefined,
    status: apiStatus,
  };

  const { data, error, isLoading, isFetching } = useQuery({
    queryKey: ['documents', queryParams],
    queryFn: () => documentsFeatureApi.listDocuments(queryParams),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const processingCount = query.state.data?.stats?.processing ?? 0;
      return processingCount > 0 ? 4000 : false;
    },
  });

  const stats = useMemo(() => {
    return (
      data?.stats ?? {
        total: 0,
        ready: 0,
        processing: 0,
        failed: 0,
      }
    );
  }, [data?.stats]);

  const documents = data?.items ?? [];
  const paginatedDocuments = documents;

  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize) || 1;

  useEffect(() => {
    if (data && totalPages > 0 && page > totalPages) {
      setPage(totalPages);
    }
  }, [data, page, totalPages]);

  return {
    search,
    setSearch: handleSetSearch,
    statusFilter,
    setStatusFilter: handleSetStatusFilter,
    page,
    setPage,
    pageSize,
    setPageSize: handleSetPageSize,
    stats,
    documents,
    paginatedDocuments,
    totalPages,
    error,
    isLoading,
    isFetching,
    isTableReady: !isLoading || !!data,
    data,
  };
}
