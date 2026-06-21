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
        <div className="flex items-center gap-2 border-b border-emerald-200 bg-emerald-50 px-6 py-2.5 text-sm text-emerald-800 font-semibold">
          <CheckCircle className="size-4 shrink-0 text-emerald-600" aria-hidden="true" />
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
        <div className="flex items-center gap-2 border-b border-red-200 bg-red-50 px-6 py-3 text-sm text-red-700 font-semibold">
          <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
          {getErrorMessage(error, 'Unable to load documents.')}
        </div>
      ) : null}

      {isLoading && !data ? <DocumentTableSkeleton /> : null}

      {!error && isTableReady && documents.length === 0 && stats.total === 0 ? (
        <div className="flex flex-col items-center gap-4 px-6 py-24 text-center">
          <div className="flex size-14 items-center justify-center rounded-sm border border-dashed border-slate-200 bg-slate-50 text-slate-400">
            <FileText className="size-6" aria-hidden="true" />
          </div>
          <div className="grid gap-1">
            <h3 className="text-base font-bold text-slate-800">No documents yet</h3>
            <p className="text-sm text-slate-500 max-w-xs">
              Upload your first SLM to start the evaluation workflow.
            </p>
          </div>
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white h-10 px-5 rounded-sm text-xs font-bold tracking-wider uppercase transition-colors"
          >
            <Upload className="size-3.5" aria-hidden="true" />
            Upload your first SLM
          </Link>
        </div>
      ) : null}

      {!error && isTableReady && documents.length === 0 && stats.total > 0 ? (
        <div className="flex flex-col items-center gap-2 px-6 py-24 text-center">
          <h3 className="text-base font-bold text-slate-800">No matches</h3>
          <p className="text-sm text-slate-500">Try a different search term or filter.</p>
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
