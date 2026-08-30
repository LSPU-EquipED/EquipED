import { useState, useMemo, useEffect } from 'react';
import { Loader2, AlertTriangle, ChevronLeft, ChevronRight, Flag } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
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
    if (!activeGroup) return [];
    return Array.from(new Set(activeGroup.chunks.map((c) => c.pageNumber))).sort((a, b) => a - b);
  }, [activeGroup]);

  // Current page state
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Synchronize current page when available pages change
  useEffect(() => {
    if (availablePages.length > 0 && !availablePages.includes(currentPage)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCurrentPage(availablePages[0]);
    }
  }, [availablePages, currentPage]);

  // Filter chunks for current page
  const chunksOnPage = useMemo(() => {
    if (!activeGroup) return [];
    return activeGroup.chunks.filter((c) => c.pageNumber === currentPage);
  }, [activeGroup, currentPage]);

  // Count flags per page for the current selected agent
  const pageFlagCounts = useMemo(() => {
    const counts = new Map<number, number>();
    if (!activeGroup || !selectedFlags) return counts;
    for (const flag of selectedFlags) {
      if (flag.chunk_id) {
        const chunk = chunkMap.get(flag.chunk_id);
        if (chunk && chunk.documentId === activeGroup.documentId) {
          counts.set(chunk.pageNumber, (counts.get(chunk.pageNumber) || 0) + 1);
        }
      }
    }
    return counts;
  }, [activeGroup, selectedFlags, chunkMap]);

  // Document-wide flags (no chunk_id assigned)
  const generalFlags = useMemo(() => {
    return selectedFlags.filter((flag) => !flag.chunk_id);
  }, [selectedFlags]);

  const totalFlagsCount = selectedFlags.length;

  // Sidebar flag index visibility
  const [showFlagIndex, setShowFlagIndex] = useState<boolean>(false);

  // Page navigation helpers
  const handlePrevPage = () => {
    const idx = availablePages.indexOf(currentPage);
    if (idx > 0) {
      setCurrentPage(availablePages[idx - 1]);
    }
  };

  const handleNextPage = () => {
    const idx = availablePages.indexOf(currentPage);
    if (idx >= 0 && idx < availablePages.length - 1) {
      setCurrentPage(availablePages[idx + 1]);
    }
  };

  const handleFlagClick = (flag: EvaluationFlagItem) => {
    if (!flag.chunk_id) return;
    const linkedChunk = chunkMap.get(flag.chunk_id);
    if (!linkedChunk) return;

    setCurrentPage(linkedChunk.pageNumber);

    setTimeout(() => {
      const el = window.document.getElementById(`chunk-${linkedChunk.chunkId}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('bg-accent-soft');
        setTimeout(() => {
          el.classList.remove('bg-accent-soft');
        }, 1500);
      }
    }, 150);
  };

  return (
    <section className="flex h-full min-h-0 flex-col bg-canvas">
      {/* Dynamic Header Toolbar */}
      <div className="flex flex-col gap-3 border-b border-border bg-surface px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {documentTextGroups.length > 1 ? (
              <>
                <select
                  value={activeGroupIndex}
                  onChange={(e) => {
                    setActiveGroupIndex(Number(e.target.value));
                    setCurrentPage(1);
                  }}
                  className="bg-transparent text-sm font-bold text-text outline-none cursor-pointer focus:ring-0"
                >
                  {documentTextGroups.map((group, idx) => (
                    <option key={group.documentId} value={idx}>
                      Document {group.documentId.slice(0, 8)}...
                    </option>
                  ))}
                </select>
                <span className="shrink-0 inline-flex items-center rounded-sm bg-surface-subtle px-2 py-0.5 text-[10px] font-medium text-text-muted border border-border">
                  {selectedAgentLabel}
                </span>
              </>
            ) : (
              <span className="inline-flex items-center gap-2 text-xs font-bold text-text-muted uppercase tracking-wider select-none">
                <span className="shrink-0 inline-flex items-center rounded-sm bg-primary-soft text-primary px-2.5 py-1 text-[10px] font-extrabold border border-primary/20 uppercase tracking-widest">
                  {selectedAgentLabel}
                </span>
                <span>Ledger Preview</span>
              </span>
            )}
          </div>
        </div>

        {/* Pager and Sidebar Controls */}
        {availablePages.length > 0 && (
          <div className="flex items-center gap-2">
            <div className="flex items-center border border-border rounded-sm bg-surface p-0.5">
              <button
                type="button"
                onClick={handlePrevPage}
                disabled={currentPage === availablePages[0]}
                className="inline-flex size-7 items-center justify-center text-text-muted hover:bg-surface-subtle hover:text-text disabled:opacity-30 disabled:hover:bg-transparent transition-colors cursor-pointer"
                aria-label="Previous Page"
              >
                <ChevronLeft className="size-4" />
              </button>

              <div className="px-2">
                <select
                  value={currentPage}
                  onChange={(e) => setCurrentPage(Number(e.target.value))}
                  className="bg-transparent text-xs font-semibold text-text outline-none cursor-pointer focus:ring-0 border-0 p-0"
                >
                  {availablePages.map((page) => {
                    const count = pageFlagCounts.get(page) || 0;
                    return (
                      <option key={page} value={page}>
                        Page {page} of {availablePages.length} {count > 0 ? `(${count} ⚑)` : ''}
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
                <ChevronRight className="size-4" />
              </button>
            </div>

            <button
              type="button"
              onClick={() => setShowFlagIndex(!showFlagIndex)}
              className={`inline-flex h-8 items-center gap-1.5 rounded-sm border px-3 text-xs font-bold uppercase tracking-wider transition-colors cursor-pointer ${
                showFlagIndex
                  ? 'border-primary bg-primary-soft text-primary'
                  : 'border-border bg-surface text-text-muted hover:bg-surface-subtle hover:text-text'
              }`}
            >
              <Flag className={`size-3.5 ${showFlagIndex ? 'fill-current' : ''}`} />
              Index {totalFlagsCount > 0 ? `(${totalFlagsCount})` : ''}
            </button>
          </div>
        )}
      </div>

      {/* Main Workspace Split */}
      <div className="flex flex-1 min-h-0 relative">
        {/* Loading / Processing States overlay */}
        {isLoading || isResolvingEval || submitIsPending ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface/70">
            <div className="flex items-center gap-3 rounded-sm border border-border bg-surface px-5 py-4 text-xs font-bold text-text-muted uppercase tracking-wider shadow-sm">
              <Loader2 className="size-4 animate-spin text-primary" aria-hidden="true" />
              {isResolvingEval
                ? 'Checking for existing evaluation…'
                : submitIsPending
                  ? 'Submitting new evaluation…'
                  : 'Loading SLM content...'}
            </div>
          </div>
        ) : null}

        {/* Reading Canvas Area */}
        <div className="flex-1 overflow-y-auto p-6 md:p-8 flex flex-col items-center">
          {!!error && (
            <div className="w-full max-w-2xl rounded-sm border border-destructive/20 bg-destructive-soft px-4 py-3 text-sm text-destructive font-semibold mb-6">
              {getErrorMessage(error, 'Unable to load the selected document.')}
            </div>
          )}

          {isResolveError && (
            <div className="w-full max-w-2xl rounded-sm border border-destructive/20 bg-destructive-soft px-4 py-3 text-sm text-destructive font-semibold mb-6">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                <div className="flex-1">
                  <p className="font-semibold">
                    {getErrorMessage(resolveError, 'Failed to start evaluation.')}
                  </p>
                  <button
                    type="button"
                    className="mt-2 inline-flex h-8 items-center justify-center border border-destructive/30 hover:bg-destructive/10 text-destructive px-3 rounded-sm text-xs font-bold tracking-wide uppercase transition-colors focus:outline-none focus:ring-2 focus:ring-ring"
                    onClick={() => refetchResolve()}
                  >
                    Retry
                  </button>
                </div>
              </div>
            </div>
          )}

          {submitIsError && (
            <div className="w-full max-w-2xl rounded-sm border border-destructive/20 bg-destructive-soft px-4 py-3 text-sm text-destructive font-semibold mb-6">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                <div className="flex-1">
                  <p className="font-semibold">
                    {getErrorMessage(submitError, 'Failed to start evaluation.')}
                  </p>
                  <button
                    type="button"
                    className="mt-2 inline-flex h-8 items-center justify-center border border-destructive/30 hover:bg-destructive/10 text-destructive px-3 rounded-sm text-xs font-bold tracking-wide uppercase transition-colors focus:outline-none focus:ring-2 focus:ring-ring"
                    onClick={handleRetrySubmit}
                  >
                    Retry
                  </button>
                </div>
              </div>
            </div>
          )}

          {!isLoading && !error && activeGroup && (
            <div className="w-full max-w-2xl">
              {/* Document-Wide Flags View (Show only on page 1) */}
              {currentPage === (availablePages[0] || 1) && generalFlags.length > 0 && (
                <div className="mb-6 rounded-sm border border-warning/30 bg-warning-soft p-4">
                  <div className="flex items-center gap-2 text-xs font-bold text-warning uppercase tracking-wider">
                    <AlertTriangle className="size-4 text-warning" />
                    General Document-Wide Flags
                  </div>
                  <div className="mt-3 space-y-3">
                    {generalFlags.map((flag) => (
                      <div
                        key={flag.flag_id}
                        className="border-t border-border pt-3 first:border-0 first:pt-0"
                      >
                        <div className="flex items-center gap-2">
                          <span className="rounded-full bg-warning-soft px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider text-warning border border-warning/30">
                            Score {formatScore(flag.score)}/4
                          </span>
                          <span className="text-xs font-semibold text-text">
                            {flag.criterion_text}
                          </span>
                        </div>
                        {flag.justification && (
                          <p className="mt-1.5 text-xs leading-relaxed text-text-muted bg-surface p-2 border border-border rounded-sm">
                            {cleanJustification(flag.justification)}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* The Faculty Ledger sheet container */}
              <div className="relative border border-border bg-surface p-8 md:p-12 shadow-none rounded-sm min-h-[600px] flex flex-col justify-between">
                {/* Ledger Sheet Framing Details */}
                <div className="absolute inset-x-0 top-0 h-1.5 bg-primary" />
                <div className="absolute inset-x-8 top-3 flex items-center justify-between border-b border-border pb-2 text-[9px] font-bold text-text-muted uppercase tracking-widest select-none">
                  <span>LSPU SCC Faculty Ledger</span>
                  <span>
                    Page {currentPage} of {availablePages.length}
                  </span>
                </div>

                {/* Page Content Chunks */}
                <article className="mt-6 flex-1 space-y-8 text-sm leading-[1.6] text-text">
                  {chunksOnPage.length > 0 ? (
                    chunksOnPage.map((chunk) => {
                      const chunkFlags = selectedFlags.filter((f) => f.chunk_id === chunk.chunkId);
                      const hasFlags = chunkFlags.length > 0;
                      return (
                        <section
                          key={chunk.chunkId}
                          id={`chunk-${chunk.chunkId}`}
                          className={`rounded-sm transition-all duration-300 ${
                            hasFlags
                              ? 'border-l-4 border-l-warning bg-warning-soft/30 px-4 py-3 space-y-4'
                              : 'border-l-4 border-l-transparent px-4 py-1'
                          }`}
                        >
                          {/* Chunk Text Content */}
                          <div className="space-y-3 font-normal text-text">
                            {chunk.text.split(/\n{2,}/).map((paragraph, paragraphIndex) => (
                              <p key={`${chunk.chunkId}-${paragraphIndex}`}>{paragraph}</p>
                            ))}
                          </div>

                          {/* Chunk Flags Inline details */}
                          {hasFlags && (
                            <div className="mt-4 pt-3 border-t border-warning/30 space-y-3">
                              {chunkFlags.map((flag) => (
                                <div
                                  key={flag.flag_id}
                                  className="rounded-sm border border-warning/30 bg-surface p-3 shadow-none"
                                >
                                  <div className="flex items-center gap-2">
                                    <Flag className="size-3.5 text-warning fill-current" />
                                    <span className="rounded-full bg-warning-soft px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider text-warning border border-warning/40">
                                      Score {formatScore(flag.score)}/4
                                    </span>
                                    <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">
                                      {selectedAgentLabel} Violation
                                    </span>
                                  </div>
                                  <h4 className="mt-2 text-xs font-bold leading-normal text-text">
                                    {flag.criterion_text}
                                  </h4>
                                  {flag.justification && (
                                    <p className="mt-1.5 text-xs leading-[1.5] text-text-muted bg-surface-subtle p-2 border border-border rounded-sm font-medium">
                                      {cleanJustification(flag.justification)}
                                    </p>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </section>
                      );
                    })
                  ) : (
                    <div className="flex h-64 flex-col items-center justify-center text-text-muted">
                      <p className="text-sm font-semibold">Empty Page</p>
                      <p className="text-xs">No text chunks extracted for page {currentPage}.</p>
                    </div>
                  )}
                </article>

                {/* Ledger Sheet Footer Details */}
                <div className="mt-12 border-t border-border pt-3 flex items-center justify-between text-[9px] font-bold text-text-muted uppercase tracking-widest select-none">
                  <span>Document ID: {activeGroup.documentId.slice(0, 8)}...</span>
                  <span>ADVISORY REPORT — CONFIRM VIA SCORECARD</span>
                </div>
              </div>
            </div>
          )}

          {!isLoading && !error && !activeGroup && (
            <div className="w-full max-w-2xl rounded-sm border border-border bg-surface p-8 text-center text-text-muted">
              <p className="font-semibold">No Content Available</p>
              <p className="text-xs mt-1">No extracted SLM text is available for this document.</p>
            </div>
          )}
        </div>

        {/* Right Collapsible Sidebar: Flag Index list */}
        {showFlagIndex && (
          <div className="w-80 border-l border-border bg-surface flex flex-col flex-shrink-0 animate-in slide-in-from-right duration-200">
            <div className="flex items-center justify-between border-b border-border px-4 py-3 bg-surface-subtle">
              <span className="text-xs font-bold text-text uppercase tracking-wider">
                {selectedAgentLabel} Flag Index
              </span>
              <button
                type="button"
                onClick={() => setShowFlagIndex(false)}
                className="text-xs font-semibold text-text-muted hover:text-text uppercase cursor-pointer"
              >
                Close
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {totalFlagsCount > 0 ? (
                selectedFlags.map((flag) => {
                  const linkedChunk = flag.chunk_id ? chunkMap.get(flag.chunk_id) : null;
                  return (
                    <button
                      key={flag.flag_id}
                      onClick={() => handleFlagClick(flag)}
                      className="w-full text-left rounded-sm border border-border bg-surface p-3 transition-colors hover:border-primary hover:bg-surface-subtle group focus:outline-none focus:ring-1 focus:ring-ring cursor-pointer"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5">
                          <Flag className="size-3 text-warning fill-current" />
                          <span className="rounded-full bg-warning-soft px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wider text-warning border border-warning/30">
                            Score {formatScore(flag.score)}/4
                          </span>
                        </div>
                        {linkedChunk && (
                          <span className="text-[10px] font-bold text-text-muted group-hover:text-primary">
                            Page {linkedChunk.pageNumber}
                          </span>
                        )}
                      </div>
                      <p className="mt-2 text-xs font-bold leading-normal text-text line-clamp-2">
                        {flag.criterion_text}
                      </p>
                      {flag.justification && (
                        <p className="mt-1 text-[10px] leading-relaxed text-text-muted line-clamp-2">
                          {cleanJustification(flag.justification)}
                        </p>
                      )}
                    </button>
                  );
                })
              ) : (
                <div className="text-center text-xs text-text-muted py-8">
                  No flags detected for this domain.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
