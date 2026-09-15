import { useEffect, useMemo, useState } from 'react';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/shared/api/documents.api';
import type { DocumentApiStatus, ListDocumentsParams } from '@/shared/api/documents.api';
import type { ClientDocument, DocumentStats } from '@/shared/types/documents';
import type { TargetAgent } from '@/shared/types/evaluations';

export type StorageProgramFilter = 'ALL' | 'BSCS' | 'BSInfoTech';
export type StorageStatusFilter = 'all' | 'PROCESSED' | 'PROCESSING' | 'FAILED';

export interface StorageRepositoryMetrics {
  totalModules: number;
  totalIndexedPages: number;
  bscsCount: number;
  bsInfoTechCount: number;
  ocrVerifiedCount: number;
}

function mapStatusToApi(filter: StorageStatusFilter): DocumentApiStatus | undefined {
  switch (filter) {
    case 'PROCESSED':
      return 'ready';
    case 'PROCESSING':
      return 'processing';
    case 'FAILED':
      return 'failed';
    default:
      return undefined;
  }
}

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
  const [evaluatingTarget, setEvaluatingTarget] = useState<{
    doc: ClientDocument;
    agent: TargetAgent;
  } | null>(null);

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

  const { data, error, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['slm-storage-repository', queryParams],
    queryFn: () => documentsApi.listDocuments(queryParams),
    placeholderData: keepPreviousData,
  });

  const documents = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize) || 1;

  // Derive repository summary metrics across all available modules
  const metrics: StorageRepositoryMetrics = useMemo(() => {
    const items = documents;
    let totalPages = 0;
    let bscs = 0;
    let bsInfoTech = 0;
    let ocrCount = 0;

    for (const doc of items) {
      totalPages += doc.pageCount ?? 0;
      if (doc.program === 'BSCS') bscs += 1;
      else if (doc.program === 'BSInfoTech') bsInfoTech += 1;
      if (doc.hasOcrPages) ocrCount += 1;
    }

    return {
      totalModules: total,
      totalIndexedPages: totalPages,
      bscsCount: bscs,
      bsInfoTechCount: bsInfoTech,
      ocrVerifiedCount: ocrCount,
    };
  }, [documents, total]);

  const stats: DocumentStats = useMemo(() => {
    return {
      total: data?.stats?.total ?? 0,
      ready: data?.stats?.ready ?? 0,
      processing: data?.stats?.processing ?? 0,
      failed: data?.stats?.failed ?? 0,
    };
  }, [data?.stats]);

  // Adjust page boundary if total reduced
  useEffect(() => {
    if (data && totalPages > 0 && page > totalPages) {
      setPage(totalPages);
    }
  }, [data, page, totalPages]);

  const handleUploadComplete = () => {
    setIsUploadOpen(false);
    void queryClient.invalidateQueries({ queryKey: ['slm-storage-repository'] });
    void refetch();
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
    isFetching,
    error,
    refetch,
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
    evaluatingTarget,
    setEvaluatingTarget,
    handleUploadComplete,
  };
}
