import { Warning, CheckCircle, Clock, Spinner, ArrowLeft } from '@phosphor-icons/react';
import { Badge, Skeleton, cn } from '@equiped/ui';
import { AlignmentHistoryList } from '../components/AlignmentHistoryList';
import { AlignmentCheckControls } from '../components/AlignmentCheckControls';
import { AlignmentCheckMetrics } from '../components/AlignmentCheckMetrics';
import { AlignmentCheckWorkbench } from '../components/AlignmentCheckWorkbench';
import { useAlignmentCheckFeature } from '../hooks/useAlignmentCheckFeature';

export function AlignmentCheckPage() {
  const {
    documentId,
    courseId,
    activeCheckId,
    readingPaneRef,
    coursesLoading,
    runCheck,
    activeCheck,
    pagesData,
    selectedDocument,
    selectedEligibility,
    pickerDocuments,
    canRunCheck,
    runErrorState,
    activeLoadErrorState,
    activeFailureState,
    coverage,
    displayedSummary,
    isBoundedResult,
    coverageText,
    courseOptions,
    selectedDocumentSupportNotice,
    handleRun,
    handleSelectHistoryItem,
    handleDocumentChange,
    handleCourseChange,
    handleClearActiveCheck,
  } = useAlignmentCheckFeature();

  return (
    <div className="mx-auto flex h-full max-w-[108rem] flex-col gap-7 px-4 py-6 sm:px-7 sm:py-8">
      {/* Integrated Control Toolbar */}
      <AlignmentCheckControls
        documentId={documentId}
        courseId={courseId}
        pickerDocuments={pickerDocuments}
        selectedDocument={selectedDocument}
        selectedEligibility={selectedEligibility}
        courseOptions={courseOptions}
        coursesLoading={coursesLoading}
        canRunCheck={canRunCheck}
        isPending={runCheck.isPending}
        isChecking={runCheck.isPending}
        onDocumentChange={handleDocumentChange}
        onCourseChange={handleCourseChange}
        onRun={handleRun}
      />

      {selectedDocumentSupportNotice ? (
        <div className="flex items-center gap-2 rounded-xs border border-warning/30 bg-warning-soft px-4 py-2.5 text-xs font-medium text-warning">
          <Clock className="size-4 shrink-0" aria-hidden="true" />
          <span>{selectedDocumentSupportNotice}</span>
        </div>
      ) : null}

      {!documentId || !courseId ? (
        <div className="rounded-xs border border-border bg-surface-subtle/50 px-4 py-2.5 text-xs text-text-muted">
          Pick a supported SLM document and a target course above to evaluate curriculum alignment.
        </div>
      ) : null}

      {runCheck.isPending ? (
        <div className="flex items-center gap-2 rounded-xs border border-primary/25 bg-primary-soft/30 px-4 py-3 text-xs font-semibold text-primary">
          <Spinner className="size-4 animate-spin shrink-0 text-primary" aria-hidden="true" />
          <span>Running curriculum alignment check against syllabus objectives…</span>
        </div>
      ) : null}

      {runErrorState ? (
        <div className="rounded-sm border border-destructive/25 bg-destructive-soft p-3.5 text-xs font-medium text-destructive">
          <div className="mb-1 flex items-center gap-2 font-semibold">
            <Warning className="size-4 shrink-0" aria-hidden="true" />
            <span>{runErrorState.title}</span>
          </div>
          <p>{runErrorState.message}</p>
          {runErrorState.kind === 'rate_limited' && runErrorState.retryAfterSeconds !== null ? (
            <p className="mt-1 font-bold tabular-nums">
              Retry in {runErrorState.retryAfterSeconds} second
              {runErrorState.retryAfterSeconds === 1 ? '' : 's'}.
            </p>
          ) : null}
        </div>
      ) : null}

      {/* History View (When no check is active) */}
      {!runCheck.isPending &&
      !runErrorState &&
      activeCheckId === null ? (
        <AlignmentHistoryList onSelect={handleSelectHistoryItem} />
      ) : null}

      {/* Active Check View */}
      {activeCheckId !== null && !runCheck.isPending ? (
        <div className="flex flex-1 flex-col gap-4 overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <button
              type="button"
              onClick={handleClearActiveCheck}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-muted hover:text-text transition-colors focus-visible:outline-2 focus-visible:outline-ring rounded-xs"
            >
              <ArrowLeft className="size-3.5" aria-hidden="true" />
              <span>Back to history</span>
            </button>

            <div className="flex flex-wrap items-center gap-2">
              {isBoundedResult ? (
                <Badge variant="warning">
                  <CheckCircle className="size-3 mr-1" aria-hidden="true" /> Partial · bounded coverage
                </Badge>
              ) : null}

              {coverage ? (
                <Badge variant="info">
                  {coverageText}
                </Badge>
              ) : null}
            </div>
          </div>

          {activeCheck.isLoading ? (
            <div
              className="flex flex-1 flex-col gap-4 overflow-hidden"
              role="status"
              aria-label="Loading curriculum alignment result"
              aria-busy="true"
            >
              {/* 5-Cell Divided Metrics Strip Skeleton */}
              <div
                className="grid grid-cols-2 divide-x divide-y divide-border overflow-hidden rounded-md border border-border bg-surface sm:grid-cols-5 sm:divide-y-0"
                aria-hidden="true"
              >
                {Array.from({ length: 5 }).map((_, index) => (
                  <div key={index} className="flex min-h-20 flex-col justify-between p-3.5 sm:p-4">
                    <div className="flex items-center justify-between gap-1.5">
                      <Skeleton className="h-3 w-20" />
                      <Skeleton className="size-3.5 rounded-full" />
                    </div>
                    <div className="mt-2 flex items-baseline gap-1.5">
                      <Skeleton className="h-7 w-10" />
                      <Skeleton className="h-2.5 w-14" />
                    </div>
                  </div>
                ))}
              </div>

              {/* Integrated Split Workbench Grid Skeleton */}
              <div className="grid flex-1 min-h-[44rem] grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)] divide-y lg:divide-y-0 lg:divide-x divide-border rounded-md border border-border bg-surface overflow-hidden">
                {/* Left Pane: SLM Reading Pane Skeleton */}
                <div className="min-w-0 flex flex-col bg-canvas p-4 sm:p-6 space-y-4">
                  <div className="flex items-center justify-between border-b border-border bg-surface-subtle/50 px-4 py-2.5 -m-4 sm:-m-6 mb-4">
                    <Skeleton className="h-3 w-32" />
                    <div className="flex items-center gap-2">
                      <Skeleton className="size-7 rounded-sm" />
                      <Skeleton className="h-3 w-20" />
                      <Skeleton className="size-7 rounded-sm" />
                    </div>
                  </div>
                  <div className="mx-auto w-full max-w-3xl rounded-md border border-border bg-surface p-6 sm:p-8 space-y-4">
                    <Skeleton className="h-5 w-48 mb-6" />
                    {Array.from({ length: 10 }).map((_, index) => (
                      <Skeleton
                        key={index}
                        className={cn(
                          'h-3.5',
                          index % 4 === 3 ? 'w-3/5' : index % 2 === 1 ? 'w-4/5' : 'w-full',
                        )}
                      />
                    ))}
                  </div>
                </div>

                {/* Right Pane: Mapped Objectives Skeleton */}
                <div className="min-w-0 flex flex-col bg-surface">
                  <div className="flex items-center justify-between border-b border-border bg-surface-subtle/50 px-4 py-2.5">
                    <div className="space-y-1">
                      <Skeleton className="h-3.5 w-48" />
                      <Skeleton className="h-2.5 w-64" />
                    </div>
                    <Skeleton className="h-3.5 w-20" />
                  </div>
                  <div className="p-4 space-y-3 flex-1 overflow-hidden">
                    {Array.from({ length: 4 }).map((_, index) => (
                      <div
                        key={index}
                        className="rounded-sm border border-border bg-surface p-4 space-y-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1.5 flex-1">
                            <Skeleton className="h-3 w-16" />
                            <Skeleton className="h-4 w-5/6" />
                          </div>
                          <Skeleton className="h-5 w-20 rounded-xs shrink-0" />
                        </div>
                        <Skeleton className="h-3 w-full" />
                        <Skeleton className="h-1.5 w-full rounded-full" />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          {activeLoadErrorState ? (
            <div className="flex items-center gap-2 rounded-sm border border-destructive/25 bg-destructive-soft p-3.5 text-xs font-medium text-destructive">
              <Warning className="size-4 shrink-0" aria-hidden="true" />
              <div>
                <span className="font-semibold block">{activeLoadErrorState.title}</span>
                <p className="mt-0.5">{activeLoadErrorState.message}</p>
              </div>
            </div>
          ) : null}

          {activeCheck.data && !activeCheck.data.success ? (
            <div className="flex items-center gap-2 rounded-sm border border-destructive/25 bg-destructive-soft p-3.5 text-xs font-medium text-destructive">
              <Warning className="size-4 shrink-0" aria-hidden="true" />
              <div>
                <span className="font-semibold block">{activeFailureState?.title ?? 'Alignment check failed'}</span>
                <p className="mt-0.5">{activeFailureState?.message ?? 'Unknown failure'}</p>
              </div>
            </div>
          ) : null}

          {activeCheck.data && activeCheck.data.success ? (
            <>
              {/* 5-Cell Divided Institutional Metrics Strip */}
              {displayedSummary ? (
                <AlignmentCheckMetrics summary={displayedSummary} />
              ) : null}

              {/* Integrated Split Workbench Grid */}
              <AlignmentCheckWorkbench
                readingPaneRef={readingPaneRef}
                pages={pagesData?.pages ?? []}
                checkData={activeCheck.data}
                coverageScope={
                  coverage?.kind === 'bounded' ? 'bounded' : coverage?.kind === 'legacy' ? 'legacy_unknown' : 'full'
                }
              />
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
