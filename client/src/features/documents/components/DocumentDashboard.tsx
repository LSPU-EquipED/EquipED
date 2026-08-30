import { useEffect, useMemo, useState } from 'react';
import { useLocation } from '@tanstack/react-router';
import { CheckCircle, FileText, TriangleAlert } from 'lucide-react';

import { getErrorMessage } from '@/shared/api/http';
import { useLatestEvaluations } from '@/shared/hooks/useLatestEvaluations';
import { TYPOGRAPHY } from '@/shared/constants/theme';
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
    if (!flashId) return;
    const timer = setTimeout(() => setFlashId(null), 6000);
    return () => clearTimeout(timer);
  }, [flashId]);

  return (
    <section className="flex w-full flex-col pb-20">
      <header className="border-b border-border bg-surface px-6 md:px-8 py-5">
        <div>
          <p className={TYPOGRAPHY.labelMuted}>
            Faculty Workspace
          </p>
          <h1 className={cn(TYPOGRAPHY.headingLg, 'mt-0.5')}>My SLMs</h1>
          <p className="mt-1 text-xs font-medium text-text-muted">
            Manage your uploaded Self-Learning Modules and start automated quality evaluations.
          </p>
        </div>
      </header>

      {flashId ? (
        <div className="flex items-center gap-2 border-b border-success/30 bg-success-soft px-6 md:px-8 py-2.5 text-sm text-success font-semibold">
          <CheckCircle className="size-4 shrink-0 text-success" aria-hidden="true" />
          Document uploaded successfully and is now available in My SLMs.
        </div>
      ) : null}

      <DocumentFilterBar
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        stats={stats}
        documentsCount={documents.length}
        totalFiltered={data?.total}
        isTableReady={isTableReady}
      />

      <DocumentActionBar search={search} setSearch={setSearch} />

      {error ? (
        <div className="flex items-center gap-2 border-b border-destructive/30 bg-destructive-soft px-6 md:px-8 py-3 text-sm text-destructive font-semibold">
          <TriangleAlert className="size-4 shrink-0 text-destructive" aria-hidden="true" />
          {getErrorMessage(error, 'Unable to load documents.')}
        </div>
      ) : null}

      {isLoading && !data ? <DocumentTableSkeleton /> : null}

      {!error && isTableReady && documents.length === 0 ? (
        <div className="border-b border-border px-6 md:px-8 py-4">
          <div className="flex items-center gap-3 rounded-sm border border-dashed border-border bg-surface-subtle px-4 py-3">
            <FileText className="size-4 text-text-muted shrink-0" aria-hidden="true" />
            <span className="text-sm font-semibold text-text">
              {stats.total === 0
                ? 'No SLMs uploaded yet. Use the Upload SLM button above to add course learning materials.'
                : 'No documents match your search.'}
            </span>
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
    </section>
  );
}
