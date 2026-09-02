import { useState, useMemo, useEffect } from 'react';
import {
  CaretLeft,
  CaretRight,
  FileText,
  Flag,
  MagnifyingGlass,
  Spinner,
  WarningCircle,
} from '@phosphor-icons/react';
import { getErrorMessage } from '@/shared/api/http';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { cn } from '@/shared/components/utils';
import type { ClientDocument, ClientDocumentChunk } from '@/shared/types/documents';
import type { EvaluationFlagItem } from '../types';
import { cleanJustification, formatScore } from '../utils/scoreHelpers';

type DocumentTextGroup = {
  documentId: string;
  chunks: ClientDocumentChunk[];
};

type DocumentPaneProps = {
  document: ClientDocument | null | undefined;
  isLoading: boolean;
  error: unknown;
  isResolvingEval: boolean;
  submitIsPending: boolean;
  isResolveError: boolean;
  resolveError: unknown;
  refetchResolve: () => void;
  submitIsError: boolean;
  submitError: unknown;
  handleRetrySubmit: () => void;
  documentTextGroups: DocumentTextGroup[];
  selectedFlags: EvaluationFlagItem[];
  chunkMap: Map<string, ClientDocumentChunk>;
  selectedAgentLabel: string;
};

function DocumentPaneSkeleton() {
  return (
    <div className="w-full max-w-2xl space-y-6" role="status" aria-label="Loading document text">
      <div className="space-y-3 rounded-sm border border-border bg-surface p-5">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-6 w-3/4 max-w-lg" />
        <Skeleton className="h-3 w-1/2 max-w-sm" />
      </div>
      <div className="space-y-4 rounded-sm border border-border bg-surface p-5 sm:p-6">
        <Skeleton className="h-4 w-48" />
        {Array.from({ length: 9 }).map((_, index) => (
          <Skeleton
            key={index}
            className={cn('h-3', index % 4 === 3 ? 'w-2/3' : 'w-full')}
          />
        ))}
      </div>
    </div>
  );
}

export function DocumentPane({
  document: _document,
  isLoading,
  error,
  isResolvingEval,
  submitIsPending,
  isResolveError,
  resolveError,
  refetchResolve,
  submitIsError,
  submitError,
  handleRetrySubmit,
  documentTextGroups,
  selectedFlags,
  chunkMap,
  selectedAgentLabel,
}: DocumentPaneProps) {
  // Active group selection (supports multiple documents, defaults to first)
  const [activeGroupIndex, setActiveGroupIndex] = useState<number>(0);
  const activeGroup = documentTextGroups[activeGroupIndex] || documentTextGroups[0];

  // Get unique page numbers in sorted order
  const availablePages = useMemo(() => {
    if (!activeGroup?.chunks?.length) return [];
    const pages = Array.from(new Set(activeGroup.chunks.map((c) => c.pageNumber))).sort(
      (a, b) => a - b,
    );
    return pages;
  }, [activeGroup]);

  // Current page state
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Synchronize current page when available pages change
  useEffect(() => {
    if (availablePages.length > 0 && !availablePages.includes(currentPage)) {
      setCurrentPage(availablePages[0]);
    }
  }, [availablePages, currentPage]);

  // Filter chunks for current page
  const chunksOnPage = useMemo(() => {
    if (!activeGroup?.chunks) return [];
    return activeGroup.chunks.filter((c) => c.pageNumber === currentPage);
  }, [activeGroup, currentPage]);

  // Count flags per page for the current selected agent
  const pageFlagCounts = useMemo(() => {
    const counts = new Map<number, number>();
    for (const flag of selectedFlags) {
      if (!flag.chunk_id) continue;
      const chunk = chunkMap.get(flag.chunk_id);
      if (chunk && chunk.documentId === activeGroup?.documentId) {
        counts.set(chunk.pageNumber, (counts.get(chunk.pageNumber) || 0) + 1);
      }
    }
    return counts;
  }, [activeGroup, selectedFlags, chunkMap]);

  // Document-wide flags (no chunk_id assigned)
  const generalFlags = useMemo(() => {
    return selectedFlags.filter((flag) => !flag.chunk_id);
  }, [selectedFlags]);

  const totalFlagsCount = selectedFlags.length;
  const currentPageFlagsCount = pageFlagCounts.get(currentPage) || 0;

  // Page navigation helpers
  const handlePrevPage = () => {
    const currentIndex = availablePages.indexOf(currentPage);
    if (currentIndex > 0) {
      setCurrentPage(availablePages[currentIndex - 1]);
    }
  };

  const handleNextPage = () => {
    const currentIndex = availablePages.indexOf(currentPage);
    if (currentIndex < availablePages.length - 1) {
      setCurrentPage(availablePages[currentIndex + 1]);
    }
  };

  const handleFlagClick = (flag: EvaluationFlagItem) => {
    if (!flag.chunk_id) return;
    const chunk = chunkMap.get(flag.chunk_id);
    if (chunk) {
      if (chunk.pageNumber !== currentPage) {
        setCurrentPage(chunk.pageNumber);
      }
      setTimeout(() => {
        const el = document.getElementById(`chunk-${flag.chunk_id}`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.classList.add('bg-warning-soft/60');
          setTimeout(() => {
            el.classList.remove('bg-warning-soft/60');
          }, 2000);
        }
      }, 200);
    }
  };

  return (
    <section className="flex h-full min-h-0 flex-col border-r border-border bg-canvas">
      {/* Top Document Reading Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface px-4 sm:px-6 py-2.5 shrink-0">
        {/* Document Group / Agent Context */}
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="size-4 text-text-muted shrink-0" aria-hidden="true" />
          {documentTextGroups.length > 1 ? (
            <select
              value={activeGroupIndex}
              onChange={(e) => {
                setActiveGroupIndex(Number(e.target.value));
                setCurrentPage(1);
              }}
              className="bg-transparent text-xs font-semibold text-text outline-none cursor-pointer"
            >
              {documentTextGroups.map((group, idx) => (
                <option key={group.documentId} value={idx}>
                  Document {group.documentId.slice(0, 8)}...
                </option>
              ))}
            </select>
          ) : (
            <span className="text-xs font-semibold text-text truncate">
              Document Reader
            </span>
          )}
          <span className="text-border">|</span>
          <span className="text-xs text-text-muted font-medium truncate">
            {selectedAgentLabel} Evidence
          </span>
        </div>

        {/* Page Pager & Flags Pill */}
        {availablePages.length > 0 && (
          <div className="flex items-center gap-2 shrink-0">
            {/* Page Navigation */}
            <div className="flex items-center rounded-sm border border-border bg-surface p-0.5">
              <button
                type="button"
                onClick={handlePrevPage}
                disabled={currentPage === availablePages[0]}
                className="inline-flex size-7 items-center justify-center text-text-muted hover:bg-surface-subtle hover:text-text disabled:opacity-30 disabled:hover:bg-transparent transition-colors cursor-pointer"
                aria-label="Previous Page"
              >
                <CaretLeft className="size-3.5" aria-hidden="true" />
              </button>

              <div className="px-2">
                <select
                  value={currentPage}
                  onChange={(e) => setCurrentPage(Number(e.target.value))}
                  className="bg-transparent text-xs font-semibold text-text outline-none cursor-pointer border-0 p-0 tabular-nums"
                  aria-label="Jump to page"
                >
                  {availablePages.map((page) => {
                    const count = pageFlagCounts.get(page) || 0;
                    return (
                      <option key={page} value={page}>
                        Page {page} of {availablePages.length} {count > 0 ? `(${count} ⚠️)` : ''}
                      </option>
                    );
                  })}
                </select>
              </div>

              <button
                type="button"
                onClick={handleNextPage}
                disabled={currentPage === availablePages[availablePages.length - 1]}
                className="inline-flex size-7 items-center justify-center text-text-muted hover:bg-surface-subtle hover:text-text disabled:opacity-30 disabled:hover:bg-transparent transition-colors cursor-pointer"
                aria-label="Next Page"
              >
                <CaretRight className="size-3.5" aria-hidden="true" />
              </button>
            </div>

            {/* Page Flag Pill */}
            {currentPageFlagsCount > 0 ? (
              <Badge variant="warning" withDot className="hidden sm:inline-flex">
                {currentPageFlagsCount} {currentPageFlagsCount === 1 ? 'flag on page' : 'flags on page'}
              </Badge>
            ) : null}
          </div>
        )}
      </div>

      {/* Reader Body Area */}
      <div className="relative flex flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 md:p-8 justify-center">
        {/* Loading / Submitting Overlay */}
        {isLoading || isResolvingEval || submitIsPending ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface/80 p-4">
            {isResolvingEval || submitIsPending ? (
              <div className="flex items-center gap-2.5 rounded-sm border border-border bg-surface px-4 py-3 text-xs font-semibold text-text shadow-sm">
                <Spinner className="size-4 animate-spin text-primary" aria-hidden="true" />
                <span>
                  {isResolvingEval ? 'Checking for existing evaluation…' : 'Submitting evaluation…'}
                </span>
              </div>
            ) : (
              <DocumentPaneSkeleton />
            )}
          </div>
        ) : null}

        {/* Content Container */}
        <div className="w-full max-w-2xl space-y-6">
          {/* Error alerts */}
          {!!error && (
            <div className="rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs font-semibold text-destructive" role="alert">
              {getErrorMessage(error, 'Unable to load the selected document.')}
            </div>
          )}

          {isResolveError && (
            <div className="rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs text-destructive" role="alert">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2">
                  <WarningCircle className="size-4 shrink-0 mt-0.5" aria-hidden="true" />
                  <span className="font-semibold">
                    {getErrorMessage(resolveError, 'Failed to start evaluation.')}
                  </span>
                </div>
                <Button type="button" variant="destructive" size="sm" onClick={() => refetchResolve()}>
                  Retry
                </Button>
              </div>
            </div>
          )}

          {submitIsError && (
            <div className="rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs text-destructive" role="alert">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2">
                  <WarningCircle className="size-4 shrink-0 mt-0.5" aria-hidden="true" />
                  <span className="font-semibold">
                    {getErrorMessage(submitError, 'Failed to start evaluation.')}
                  </span>
                </div>
                <Button type="button" variant="destructive" size="sm" onClick={handleRetrySubmit}>
                  Retry
                </Button>
              </div>
            </div>
          )}

          {/* Document-Wide Flags (Page 1 Callout) */}
          {!isLoading && !error && currentPage === (availablePages[0] || 1) && generalFlags.length > 0 && (
            <div className="rounded-md border border-warning/30 bg-warning-soft/30 p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-warning">
                <WarningCircle className="size-4 text-warning" aria-hidden="true" />
                <span>General Document-Wide Observations ({generalFlags.length})</span>
              </div>
              <div className="divide-y divide-warning/20">
                {generalFlags.map((flag) => (
                  <div key={flag.flag_id} className="pt-2.5 first:pt-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-text">
                        {flag.criterion_text}
                      </span>
                      <Badge variant="warning">
                        Score {formatScore(flag.score)}/4
                      </Badge>
                    </div>
                    {flag.justification ? (
                      <p className="mt-1 text-xs text-text-muted leading-relaxed">
                        {cleanJustification(flag.justification)}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Structured Document Reading Canvas */}
          {!isLoading && !error && activeGroup && (
            <div className="rounded-md border border-border bg-surface p-6 sm:p-8 space-y-6 shadow-none">
              {/* Reading Canvas Header */}
              <div className="flex items-center justify-between border-b border-border pb-3 text-xs text-text-muted">
                <span className="font-semibold text-text">
                  Page {currentPage} of {availablePages.length}
                </span>
                <span className="text-[11px] font-medium tabular-nums">
                  {chunksOnPage.length} {chunksOnPage.length === 1 ? 'content chunk' : 'content chunks'}
                </span>
              </div>

              {/* Document Text Chunks */}
              <div className="space-y-6 text-[14.5px] leading-[1.7] text-text font-normal">
                {chunksOnPage.length > 0 ? (
                  chunksOnPage.map((chunk) => {
                    const chunkFlags = selectedFlags.filter((f) => f.chunk_id === chunk.chunkId);
                    const hasFlags = chunkFlags.length > 0;

                    return (
                      <article
                        key={chunk.chunkId}
                        id={`chunk-${chunk.chunkId}`}
                        className={cn(
                          'rounded-sm p-3 transition-colors duration-300',
                          hasFlags ? 'border border-warning/30 bg-warning-soft/10' : 'border-transparent',
                        )}
                      >
                        {/* Chunk Body Paragraphs */}
                        <div className="space-y-3">
                          {chunk.text.split(/\n{2,}/).map((para, pIdx) => (
                            <p key={`${chunk.chunkId}-${pIdx}`}>{para}</p>
                          ))}
                        </div>

                        {/* Embedded Flag Callout */}
                        {hasFlags && (
                          <div className="mt-3.5 rounded-sm border border-warning/30 bg-surface p-3 space-y-2">
                            <div className="flex items-center gap-1.5 text-xs font-semibold text-warning">
                              <WarningCircle className="size-3.5 text-warning" aria-hidden="true" />
                              <span>Specialist Finding ({selectedAgentLabel})</span>
                            </div>
                            {chunkFlags.map((flag) => (
                              <div key={flag.flag_id} className="text-xs space-y-1">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-semibold text-text">
                                    {flag.criterion_text}
                                  </span>
                                  <Badge variant="warning">
                                    Score {formatScore(flag.score)}/4
                                  </Badge>
                                </div>
                                {flag.justification ? (
                                  <p className="text-text-muted leading-relaxed">
                                    {cleanJustification(flag.justification)}
                                  </p>
                                ) : null}
                              </div>
                            ))}
                          </div>
                        )}
                      </article>
                    );
                  })
                ) : (
                  <div className="py-12 text-center text-sm text-text-muted">
                    <p className="font-semibold text-text">No text available on this page</p>
                    <p className="text-xs text-text-muted mt-1">
                      Navigate to other pages using the page selector above.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
