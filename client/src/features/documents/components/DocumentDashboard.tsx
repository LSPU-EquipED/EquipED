import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from '@tanstack/react-router';
import { CheckCircle, FileText, Warning } from '@phosphor-icons/react';

import { getErrorMessage } from '@/shared/api/http';
import { useLatestEvaluations } from '@/shared/hooks/useLatestEvaluations';
import type { TargetAgent } from '@/shared/types/evaluations';
import { useSlmStorage } from '../hooks/useSlmStorage';
import { StorageMetricsStrip } from './StorageMetricsStrip';
import { StorageToolbar } from './StorageToolbar';
import { DocumentTable, DocumentTableSkeleton } from './DocumentTable';
import { DocumentPagination } from './DocumentPagination';
import { ModuleInspectorDrawer } from './ModuleInspectorDrawer';
import { StorageUploadModal } from './StorageUploadModal';

export function DocumentDashboard({ targetAgent = 'sme' }: { targetAgent?: TargetAgent }) {
  const location = useLocation();
  const navigate = useNavigate();

  const highlightId = useMemo(
    () => new URLSearchParams(location.search).get('highlight'),
    [location.search],
  );
  const [flashId, setFlashId] = useState<string | null>(highlightId ?? null);

  const {
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
    search,
    setSearch,
    programFilter,
    setProgramFilter,
    statusFilter,
    setStatusFilter,
    inspectingDoc,
    setInspectingDoc,
    isUploadOpen,
    setIsUploadOpen,
    handleUploadComplete,
  } = useSlmStorage();

  const documentIds = useMemo(
    () => documents.map((d) => d.documentId),
    [documents],
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

      {/* ── Success Flash Banner ───────────────────────────────────── */}
      {flashId ? (
        <div
          className="flex items-center gap-2 rounded-sm border border-success/30 bg-success-soft px-4 py-3 text-xs sm:text-sm text-success font-semibold"
          role="status"
        >
          <CheckCircle className="size-4 shrink-0 text-success" aria-hidden="true" />
          <span>Document uploaded successfully and is now indexed in SLM Storage.</span>
        </div>
      ) : null}

      {/* ── Error Alert ────────────────────────────────────────────── */}
      {error ? (
        <div
          className="flex items-center gap-2 rounded-sm border border-destructive/30 bg-destructive-soft px-4 py-3 text-xs sm:text-sm text-destructive font-semibold"
          role="alert"
        >
          <Warning className="size-4 shrink-0 text-destructive" aria-hidden="true" />
          <span>{getErrorMessage(error, 'Unable to load SLM repository.')}</span>
        </div>
      ) : null}

      {/* ── Top Repository Metrics Strip ───────────────────────────── */}
      <StorageMetricsStrip
        metrics={metrics}
        stats={stats}
        isLoading={isLoading}
      />

      {/* ── Storage Repository Table & Filter Workspace ────────────── */}
      <div className="space-y-3">
        <StorageToolbar
          programFilter={programFilter}
          setProgramFilter={setProgramFilter}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          search={search}
          setSearch={setSearch}
          totalModules={total}
          onOpenUpload={() => setIsUploadOpen(true)}
        />

        <div className="rounded-md border border-border bg-surface shadow-none overflow-hidden">
          {isLoading && documents.length === 0 ? <DocumentTableSkeleton /> : null}

          {!error && !isLoading && documents.length === 0 ? (
            <div className="px-6 py-16 text-center text-sm text-text-muted">
              <div className="flex flex-col items-center justify-center gap-2 max-w-sm mx-auto">
                <FileText className="size-8 text-text-muted/50" aria-hidden="true" />
                <p className="font-semibold text-text text-base">
                  {stats.total === 0
                    ? 'No SLMs in Storage Yet'
                    : 'No matching modules found'}
                </p>
                <p className="text-xs text-text-muted leading-relaxed">
                  {stats.total === 0
                    ? 'Upload course learning modules in PDF format to index them for multi-agent accreditation.'
                    : 'Try changing your program filter or searching by course code or topic.'}
                </p>
              </div>
            </div>
          ) : null}

          {!error && documents.length > 0 ? (
            <DocumentTable
              documents={documents}
              flashId={flashId}
              latestEvalsByDocId={latestEvalsByDocId}
              latestEvalsState={latestEvalsState}
              targetAgent={targetAgent}
              onInspect={(doc) => setInspectingDoc(doc)}
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
      </div>

      {/* ── File Technical Inspector Drawer ────────────────────────── */}
      <ModuleInspectorDrawer
        document={inspectingDoc}
        onClose={() => setInspectingDoc(null)}
      />

      {/* ── In-Place SLM Upload Dialog ─────────────────────────────── */}
      <StorageUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={handleUploadComplete}
      />
    </section>
  );
}
