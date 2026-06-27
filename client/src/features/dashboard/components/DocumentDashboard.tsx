import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, Link } from '@tanstack/react-router';
import { CheckCircle, FileText, TriangleAlert, Upload } from 'lucide-react';

import { getErrorMessage } from '@/shared/api/http';
import { useDocumentDashboard } from '../hooks/useDocumentDashboard';
import { DocumentFilterBar } from './DocumentFilterBar';
import { DocumentActionBar } from './DocumentActionBar';
import { DocumentTable, DocumentTableSkeleton } from './DocumentTable';
import { DocumentPagination } from './DocumentPagination';

export function DocumentDashboard() {
  const navigate = useNavigate();
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

  useEffect(() => {
    if (!flashId) return;
    const timer = setTimeout(() => setFlashId(null), 6000);
    return () => clearTimeout(timer);
  }, [flashId]);

  const openEvaluationInterface = (documentId: string) => {
    void navigate({ to: '/documents/$documentId/evaluation', params: { documentId } });
  };

  return (
    <section className="flex w-full flex-col pb-20">
      {flashId ? (
        <div className="flex items-center gap-2 border-b border-[#3b963e]/30 bg-[#3b963e]/10 px-6 py-2.5 text-sm text-[#3b963e] font-semibold">
          <CheckCircle className="size-4 shrink-0 text-[#3b963e]" aria-hidden="true" />
          Document uploaded successfully and is now ready in your inventory.
        </div>
      ) : null}

      <DocumentFilterBar
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        stats={stats}
        documentsCount={documents.length}
        isTableReady={isTableReady}
      />

      <DocumentActionBar search={search} setSearch={setSearch} />

      {error ? (
        <div className="flex items-center gap-2 border-b border-[#b91c1c]/30 bg-[#b91c1c]/10 px-6 py-3 text-sm text-[#b91c1c] font-semibold">
          <TriangleAlert className="size-4 shrink-0 text-[#b91c1c]" aria-hidden="true" />
          {getErrorMessage(error, 'Unable to load documents.')}
        </div>
      ) : null}

      {isLoading && !data ? <DocumentTableSkeleton /> : null}

      {!error && isTableReady && documents.length === 0 ? (
        <div className="border-b border-slate-200 px-6 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-dashed border-slate-200 bg-slate-50/30 px-4 py-3">
            <div className="flex items-center gap-3">
              <FileText className="size-4 text-slate-500" aria-hidden="true" />
              <span className="text-sm font-semibold text-slate-700">
                {stats.total === 0
                  ? 'No documents in your inventory.'
                  : 'No documents match your search.'}
              </span>
            </div>
            {stats.total === 0 ? (
              <Link
                to="/upload"
                className="inline-flex items-center gap-2 bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white h-8 px-3 rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors"
              >
                <Upload className="size-3.5" aria-hidden="true" />
                Upload SLM
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}

      {!error && paginatedDocuments.length > 0 ? (
        <DocumentTable
          documents={paginatedDocuments}
          flashId={flashId}
          onOpenEvaluation={openEvaluationInterface}
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
