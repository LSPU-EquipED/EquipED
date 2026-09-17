import { useEffect, useMemo, useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@equiped/api-client';
import type { ListDocumentsParams } from '@equiped/api-client';
import type { ClientDocument, DocumentStats } from '@equiped/types';
import {
  calculateStorageMetrics,
  mapStatusToApi,
  type StorageProgramFilter,
  type StorageRepositoryMetrics,
  type StorageStatusFilter,
} from '../utils/storage.utils';

export type { StorageProgramFilter, StorageStatusFilter, StorageRepositoryMetrics };

const EMPTY_DOCUMENTS: ClientDocument[] = [];
const DEFAULT_STATS: DocumentStats = {
  total: 0,
  ready: 0,
  processing: 0,
  failed: 0,
};

export function useSlmStorage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [programFilter, setProgramFilter] = useState<StorageProgramFilter>('ALL');
  const [statusFilter, setStatusFilter] = useState<StorageStatusFilter>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Modals & Drawer state
  const [inspectingDoc, setInspectingDoc] = useState<ClientDocument | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  const handleSetSearch = (val: string) => {
    setSearch(val);
    setPage(1);
  };

  const handleSetProgramFilter = (val: StorageProgramFilter) => {
    setProgramFilter(val);
    setPage(1);
  };

  const handleSetStatusFilter = (val: StorageStatusFilter) => {
    setStatusFilter(val);
    setPage(1);
  };

  const queryParams: ListDocumentsParams = useMemo(() => {
    const trimmed = search.trim();
    const apiStatus = mapStatusToApi(statusFilter);
    return {
      sourceType: 'slm',
      program: programFilter !== 'ALL' ? programFilter : undefined,
      status: apiStatus,
      search: trimmed || undefined,
      page,
      pageSize,
    };
  }, [search, programFilter, statusFilter, page, pageSize]);

  const { data, error, isLoading } = useQuery({
    queryKey: ['slm-storage-repository', queryParams],
    queryFn: () => documentsApi.listDocuments(queryParams),
    placeholderData: keepPreviousData,
  });

  const documents = data?.items ?? EMPTY_DOCUMENTS;
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize) || 1;

  // Derive repository summary metrics across all available modules
  const metrics: StorageRepositoryMetrics = useMemo(() => {
    return calculateStorageMetrics(documents, total);
  }, [documents, total]);

  const stats: DocumentStats = data?.stats ?? DEFAULT_STATS;

  // Adjust page boundary if total reduced
  useEffect(() => {
    if (data && totalPages > 0 && page > totalPages) {
      setPage(totalPages);
    }
  }, [data, page, totalPages]);

  const handleUploadComplete = () => {
    setIsUploadOpen(false);
    void queryClient.invalidateQueries({ queryKey: ['slm-storage-repository'] });
  };

  return {
    // Data & status
    documents,
    metrics,
    stats,
    total,
    page,
    setPage,
    pageSize,
    setPageSize,
    totalPages,
    isLoading,
    error,
    // Filters & Search
    search,
    setSearch: handleSetSearch,
    programFilter,
    setProgramFilter: handleSetProgramFilter,
    statusFilter,
    setStatusFilter: handleSetStatusFilter,
    // Interactive state
    inspectingDoc,
    setInspectingDoc,
    isUploadOpen,
    setIsUploadOpen,
    handleUploadComplete,
  };
}
