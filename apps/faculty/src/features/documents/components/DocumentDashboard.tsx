import { useEffect, useMemo, useState } from 'react';
import { useLocation } from '@tanstack/react-router';
import { CheckCircle, FileText, MagnifyingGlass, UploadSimple, Warning } from '@phosphor-icons/react';

import { getErrorMessage } from '@equiped/api-client';
import { Button } from '@equiped/ui';
import { useLatestEvaluations } from '@/shared/hooks/useLatestEvaluations';
import type { TargetAgent } from '@equiped/types';
import { useSlmStorage } from '../hooks/useSlmStorage';
import { StorageToolbar } from './StorageToolbar';
import { DocumentTable, DocumentTableSkeleton } from './DocumentTable';
import { DocumentPagination } from './DocumentPagination';
import { ModuleInspectorDrawer } from './ModuleInspectorDrawer';
import { StorageUploadModal } from './StorageUploadModal';
import { sortDocuments, type DocumentSortOption } from '../utils/storage.utils';

export function DocumentDashboard({ targetAgent = 'sme' }: { targetAgent?: TargetAgent }) {
  const location = useLocation();

  const highlightId = useMemo(
    () => new URLSearchParams(location.search).get('highlight'),
    [location.search],
  );
  const openUploadFromDashboard = useMemo(
    () => new URLSearchParams(location.search).get('upload') === 'true',
    [location.search],
  );
  const [flashId, setFlashId] = useState<string | null>(highlightId ?? null);
  const [sortOption, setSortOption] = useState<DocumentSortOption>('uploaded-desc');

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

  const sortedDocuments = useMemo(() => {
    return sortDocuments(documents, sortOption);
  }, [documents, sortOption]);


  const documentIds = useMemo(
    () => sortedDocuments.map((d) => d.documentId),
    [sortedDocuments],
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

  useEffect(() => {
    if (openUploadFromDashboard) {
      setIsUploadOpen(true);
    }
  }, [openUploadFromDashboard, setIsUploadOpen]);

  return (
    <section className="mx-auto flex w-full max-w-[108rem] flex-col gap-7 px-4 py-6 sm:px-7 sm:py-8">
      <h1 className="sr-only">SLM Storage</h1>

      {/* ── Success Flash Banner ───────────────────────────────────── */}
      {flashId ? (
        <div
          className="flex items-center gap-2 rounded-sm border border-success/30 bg-success-soft px-4 py-3 text-xs sm:text-sm text-success font-semibold shrink-0 animate-ledger-banner-in"
          role="status"
        >
          <CheckCircle className="size-4 shrink-0 text-success" aria-hidden="true" />
          <span>Document uploaded successfully and is now indexed in SLM Storage.</span>
        </div>
      ) : null}

      {/* ── Error Alert ────────────────────────────────────────────── */}
      {error ? (
        <div
          className="flex items-center gap-2 rounded-sm border border-destructive/30 bg-destructive-soft px-4 py-3 text-xs sm:text-sm text-destructive font-semibold shrink-0"
          role="alert"
        >
          <Warning className="size-4 shrink-0 text-destructive" aria-hidden="true" />
          <span>{getErrorMessage(error, 'Unable to load SLM repository.')}</span>
        </div>
      ) : null}

      {/* Search controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-lg">
          <MagnifyingGlass
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
            aria-hidden="true"
          />
          <input
            type="text"
            placeholder="Search course modules by title, code, or topic..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-10 w-full rounded-sm border border-input bg-surface pl-9 pr-4 text-sm text-text placeholder:text-text-muted focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label="Search course modules"
          />
        </div>
        <Button
          type="button"
          variant="primary"
          size="md"
          onClick={() => setIsUploadOpen(true)}
          className="h-10 w-full shrink-0 gap-2 px-4 text-xs font-semibold sm:w-auto"
        >
          <UploadSimple className="size-4" aria-hidden="true" />
          <span>Upload SLM</span>
        </Button>
      </div>

      {/* Filter and sort controls */}
      <div>
        <StorageToolbar
          programFilter={programFilter}
          setProgramFilter={setProgramFilter}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          sortOption={sortOption}
          setSortOption={setSortOption}
          totalModules={total}
          bscsCount={metrics.bscsCount}
          bsInfoTechCount={metrics.bsInfoTechCount}
          onResetFilters={() => {
            setProgramFilter('ALL');
            setStatusFilter('all');
          }}
        />
      </div>

      {/* Repository ledger */}
      <div
        className="flex flex-col overflow-hidden rounded-sm border border-border bg-surface"
        role="region"
        aria-label="SLM Storage Repository Ledger"
      >
        <div className="min-w-0 w-full">
          {isLoading && documents.length === 0 ? <DocumentTableSkeleton /> : null}

          {!error && !isLoading && documents.length === 0 ? (
            <div className="flex items-center justify-center px-6 py-16 text-center text-sm text-text-muted">
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
              documents={sortedDocuments}
              flashId={flashId}
              latestEvalsByDocId={latestEvalsByDocId}
              latestEvalsState={latestEvalsState}
              targetAgent={targetAgent}
              onInspect={(doc) => setInspectingDoc(doc)}
            />
          ) : null}
        </div>

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

      {/* ── File Technical Inspector Drawer ────────────────────────── */}
      <ModuleInspectorDrawer
        document={inspectingDoc}
        latestEvaluation={
          inspectingDoc ? latestEvalsByDocId[inspectingDoc.documentId] : undefined
        }
        latestEvalsState={latestEvalsState}
        targetAgent={targetAgent}
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
