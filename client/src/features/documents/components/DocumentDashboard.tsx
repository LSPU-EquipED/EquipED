import { useEffect, useMemo, useState } from 'react';
import { useLocation, Link } from '@tanstack/react-router';
import { CheckCircle, FileText, Plus, Warning } from '@phosphor-icons/react';

import { getErrorMessage } from '@/shared/api/http';
import { useLatestEvaluations } from '@/shared/hooks/useLatestEvaluations';
import { BUTTON_STYLES, TYPOGRAPHY } from '@/shared/constants/theme';
import { cn } from '@/shared/components/utils';
import { useDocumentDashboard } from '../hooks/useDocumentDashboard';
import { DocumentFilterBar } from './DocumentFilterBar';
import { DocumentActionBar } from './DocumentActionBar';
import { DocumentTable, DocumentTableSkeleton } from './DocumentTable';
import { DocumentPagination } from './DocumentPagination';

export function DocumentDashboard() {
  const location = useLocation();

  const highlightId = useMemo(
    () => new URLSearchParams(location.search).get('highlight'),
    [location.search],
  );
  const [flashId, setFlashId] = useState<string | null>(highlightId ?? null);

  const {
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
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
    isTableReady,
    data,
  } = useDocumentDashboard();

  const documentIds = useMemo(
    () => paginatedDocuments.map((d) => d.documentId),
    [paginatedDocuments],
  );

  const {
    latestEvalsByDocId,
    isLoading: isLatestEvalsLoading,
    isError: isLatestEvalsError,
    isSuccess: isLatestEvalsSuccess,
  } = useLatestEvaluations(documentIds);

  const latestEvalsState = useMemo(
    () => ({
      isLoading: isLatestEvalsLoading,
      isError: isLatestEvalsError,
      isSuccess: isLatestEvalsSuccess,
    }),
    [isLatestEvalsLoading, isLatestEvalsError, isLatestEvalsSuccess],
  );

  useEffect(() => {
    if (flashId) {
      const timer = setTimeout(() => setFlashId(null), 6000);
      return () => clearTimeout(timer);
    }
  }, [flashId]);

  return (
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-5">
      {/* Success Flash Banner */}
      {flashId ? (
        <div className="flex items-center gap-2 rounded-sm border border-success/30 bg-success-soft px-4 py-3 text-xs sm:text-sm text-success font-semibold" role="status">
          <CheckCircle className="size-4 shrink-0 text-success" aria-hidden="true" />
          <span>Document uploaded successfully and is now available in My SLMs.</span>
        </div>
      ) : null}

      {/* Error alert */}
      {error ? (
        <div className="flex items-center gap-2 rounded-sm border border-destructive/30 bg-destructive-soft px-4 py-3 text-xs sm:text-sm text-destructive font-semibold" role="alert">
          <Warning className="size-4 shrink-0 text-destructive" aria-hidden="true" />
          <span>{getErrorMessage(error, 'Unable to load documents.')}</span>
        </div>
      ) : null}

      {/* Unified Table & Filters Wrapper */}
      <div className="rounded-md border border-border bg-surface shadow-none overflow-hidden">
        <DocumentFilterBar
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          stats={stats}
          documentsCount={documents.length}
          totalFiltered={data?.total}
          isTableReady={isTableReady}
        />

        <DocumentActionBar search={search} setSearch={setSearch} />

        {isLoading && !data ? <DocumentTableSkeleton /> : null}

        {!error && isTableReady && documents.length === 0 ? (
          <div className="px-6 py-12 text-center text-sm text-text-muted">
            <div className="flex flex-col items-center justify-center gap-2">
              <FileText className="size-6 text-text-muted/60" aria-hidden="true" />
              <p className="font-semibold text-text">
                {stats.total === 0
                  ? 'No SLMs uploaded yet. Use the Upload SLM button above to add course learning materials.'
                  : 'No documents match your search.'}
              </p>
            </div>
          </div>
        ) : null}

        {!error && paginatedDocuments.length > 0 ? (
          <DocumentTable
            documents={paginatedDocuments}
            flashId={flashId}
            latestEvalsByDocId={latestEvalsByDocId}
            latestEvalsState={latestEvalsState}
          />
        ) : null}

        {!error && documents.length > 0 ? (
          <DocumentPagination
            page={page}
            setPage={setPage}
            pageSize={pageSize}
            setPageSize={setPageSize}
            totalPages={totalPages}
          />
        ) : null}
      </div>
    </section>
  );
}
