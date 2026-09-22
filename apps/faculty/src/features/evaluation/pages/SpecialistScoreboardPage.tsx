import { Link } from "@tanstack/react-router";
import {
  ArrowRight,
  ArrowsClockwise,
  FileText,
  FolderOpen,
  WarningCircle,
} from "@phosphor-icons/react";
import { Skeleton } from "@equiped/ui";
import { cn } from "@equiped/ui";
import { BUTTON_STYLES } from "@equiped/ui";
import type { TargetAgent } from "@equiped/types";
import { AgentReviewModal } from "../components/AgentReviewModal";
import { EvaluationConfirmModal } from "../components/EvaluationConfirmModal";
import { SpecialistDirectoryView } from "../components/SpecialistDirectoryView";
import { SpecialistLaunchpad } from "../components/SpecialistLaunchpad";
import { SpecialistResultsScoreboard } from "../components/SpecialistResultsScoreboard";
import { useSpecialistWorkspace } from "../hooks/useSpecialistWorkspace";

export interface SpecialistScoreboardPageProps {
  agentId?: TargetAgent;
  documentId?: string;
}

function SpecialistWorkspaceLoading({ label }: { label: string }) {
  return (
    <div
      className="overflow-hidden rounded-md border border-border bg-surface"
      role="status"
      aria-label={`Loading ${label} specialist workspace`}
      aria-busy="true"
    >
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <Skeleton className="size-9 rounded-sm" />
          <div className="space-y-2">
            <Skeleton className="h-2.5 w-28" />
            <Skeleton className="h-4 w-48 max-w-[52vw]" />
          </div>
        </div>
        <Skeleton className="h-3 w-24" />
      </div>
      <div className="grid min-w-0 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-5 px-5 py-8 sm:px-8 sm:py-10">
          <Skeleton className="h-2.5 w-20" />
          <Skeleton className="h-8 w-96 max-w-full" />
          <Skeleton className="h-3 w-full max-w-xl" />
          <Skeleton className="h-3 w-4/5 max-w-lg" />
          <Skeleton className="mt-2 h-10 w-32" />
          <div className="mt-6 flex flex-wrap gap-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="flex items-center gap-2">
                <Skeleton className="size-6 rounded-xs" />
                <Skeleton className="h-2.5 w-20" />
              </div>
            ))}
          </div>
        </div>
        <aside className="border-t border-border bg-surface-subtle/40 px-5 py-6 sm:px-6 lg:border-l lg:border-t-0">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="mt-4 h-3 w-full" />
          <Skeleton className="mt-2 h-3 w-5/6" />
          <div className="mt-7 space-y-4 border-y border-border py-4">
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="space-y-2">
                <Skeleton className="h-2.5 w-24" />
                <Skeleton className="h-3 w-40 max-w-full" />
              </div>
            ))}
          </div>
        </aside>
      </div>
      <span className="sr-only">Loading the specialist workspace.</span>
    </div>
  );
}

function SpecialistEvaluationLoading({
  label,
  title,
  status,
}: {
  label: string;
  title: string;
  status: string;
}) {
  return (
    <section
      className="overflow-hidden rounded-md border border-border bg-surface"
      role="status"
      aria-label={`${label} evaluation in progress`}
      aria-busy="true"
    >
      <div className="grid min-w-0 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-6 p-6 sm:p-8 lg:p-10">
          <div className="flex items-center gap-3">
            <Skeleton className="size-9 rounded-sm" />
            <div className="space-y-2">
              <Skeleton className="h-2.5 w-28" />
              <Skeleton className="h-3.5 w-44" />
            </div>
          </div>
          <div className="space-y-3">
            <Skeleton className="h-2.5 w-24" />
            <h2 className="text-xl font-semibold text-text sm:text-2xl">
              {title}
            </h2>
            <Skeleton className="h-3 w-full max-w-xl" />
            <Skeleton className="h-3 w-4/5 max-w-lg" />
          </div>
          <div className="flex items-center gap-3 border-y border-border py-5">
            <Skeleton className="h-10 w-28" />
            <Skeleton className="h-10 w-28" />
            <Skeleton className="h-10 w-24" />
          </div>
          <Skeleton className="h-10 w-36" />
        </div>
        <aside className="border-t border-border bg-surface-subtle/55 px-6 py-7 sm:px-8 lg:border-l lg:border-t-0 lg:px-7">
          <div className="flex items-center justify-between gap-3">
            <div className="space-y-2">
              <Skeleton className="h-2.5 w-24" />
              <Skeleton className="h-4 w-36" />
            </div>
            <Skeleton className="size-8 rounded-sm" />
          </div>
          <div className="mt-7 space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={index}
                className="rounded-sm border border-border bg-surface px-3 py-3"
              >
                <div className="flex items-center gap-2">
                  <Skeleton className="size-6 rounded-sm" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-2.5 w-24" />
                    <Skeleton className="h-1 w-full" />
                  </div>
                </div>
                <Skeleton className="mt-3 h-2.5 w-28" />
              </div>
            ))}
          </div>
          <div className="mt-6 border-t border-border pt-4">
            <Skeleton className="h-2.5 w-full" />
            <Skeleton className="mt-2 h-2.5 w-4/5" />
          </div>
        </aside>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-subtle/35 px-5 py-3.5 text-xs sm:px-6">
        <span className="text-text-muted">Status: {status}</span>
        <span className="text-text-muted">Usually 20–30 seconds</span>
      </div>
      <span className="sr-only">
        Evaluation is running. Loading the evidence scorecard.
      </span>
    </section>
  );
}

function SpecialistResultsLoading() {
  return (
    <section
      className="min-w-0"
      role="status"
      aria-label="Loading specialist results"
      aria-busy="true"
    >
      {/* Header Skeleton matching SpecialistResultsScoreboard */}
      <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-border pb-3">
        <div className="min-w-0 flex-1 basis-72 space-y-2">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-6 w-64 max-w-full" />
          <Skeleton className="h-3 w-44" />
        </div>
        <div className="flex max-w-full flex-wrap items-center gap-2">
          <Skeleton className="h-8 w-28 rounded-sm" />
          <Skeleton className="h-8 w-36 rounded-sm" />
          <Skeleton className="size-9 rounded-sm shrink-0" />
        </div>
      </header>

      {/* Two-column layout matching SpecialistResultsScoreboard */}
      <div className="grid min-w-0 gap-4 pt-4 xl:grid-cols-[18rem_minmax(0,1fr)] xl:gap-7">
        {/* Left Column: Module Details Dossier */}
        <aside
          className="hidden min-w-0 border-r border-border pr-5 xl:block space-y-4"
          aria-label="Evaluation metadata loading"
        >
          <Skeleton className="h-3.5 w-24" />
          <div className="space-y-4 py-3">
            <div className="flex items-center justify-between gap-2 border-b border-border pb-3">
              <Skeleton className="h-5 w-20 rounded-xs" />
              <Skeleton className="h-3.5 w-24" />
            </div>
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div
                  key={index}
                  className="grid grid-cols-[5.25rem_minmax(0,1fr)] gap-2"
                >
                  <Skeleton className="h-3 w-14" />
                  <Skeleton className="h-3 w-28" />
                </div>
              ))}
            </div>
            <div className="mt-4 border-t border-border pt-3">
              <Skeleton className="h-3.5 w-24" />
            </div>
          </div>
        </aside>

        {/* Right Column: Scorecard & Criteria Ledger */}
        <section className="min-w-0 space-y-4" aria-label="Specialist scorecard loading">
          {/* Score Summary Banner */}
          <div className="border-b border-border pb-3">
            <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_13rem] md:items-center">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <Skeleton className="h-8 w-24" />
                <Skeleton className="h-6 w-28 rounded-xs" />
                <Skeleton className="h-3.5 w-28" />
                <Skeleton className="h-3.5 w-36" />
              </div>
              <div className="border-t border-border pt-3 md:border-l md:border-t-0 md:pl-4 md:pt-0">
                <Skeleton className="h-3.5 w-20 mb-2" />
                <div className="flex h-12 items-end gap-2">
                  {[70, 95, 45, 25].map((h, i) => (
                    <div key={i} className="flex min-w-0 flex-1 flex-col items-center gap-1">
                      <div className="flex h-9 w-full items-end rounded-xs bg-surface-subtle px-1">
                        <Skeleton className="w-full rounded-xs" style={{ height: `${h}%` }} />
                      </div>
                      <Skeleton className="h-2 w-2" />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Specialist Summary Accordion Skeleton */}
          <div className="border-b border-border py-2 flex items-center gap-2">
            <Skeleton className="size-3.5 rounded-xs" />
            <Skeleton className="h-3.5 w-32" />
          </div>

          {/* Criteria Breakdown Header & Triage Filter Tabs */}
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3 py-1">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-56" />
            </div>
            <div className="flex flex-wrap items-center gap-1.5 pb-2">
              <Skeleton className="h-6 w-16 rounded-xs" />
              <Skeleton className="h-6 w-28 rounded-xs" />
              <Skeleton className="h-6 w-20 rounded-xs" />
            </div>

            {/* Criteria Rows */}
            <div className="divide-y divide-border border-y border-border">
              {Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={index}
                  className="grid min-h-12 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-3 py-3 sm:px-4"
                >
                  <div className="flex min-w-0 items-center gap-2.5">
                    <Skeleton className="size-3.5 shrink-0 rounded-xs" />
                    <Skeleton className="h-3 w-12 shrink-0 font-mono" />
                    <div className="min-w-0 flex-1 space-y-1">
                      <Skeleton className={cn('h-4', index % 2 === 0 ? 'w-3/4' : 'w-1/2')} />
                    </div>
                  </div>
                  <Skeleton className="h-6 w-16 shrink-0 rounded-xs" />
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
      <span className="sr-only">Loading the specialist results.</span>
    </section>
  );
}

function SpecialistResultsError({ onRetry }: { onRetry: () => void }) {
  return (
    <section
      className="flex min-h-56 flex-col items-center justify-center gap-3 border border-destructive/30 bg-destructive-soft px-6 py-10 text-center"
      role="alert"
    >
      <WarningCircle className="size-6 text-destructive" aria-hidden="true" />
      <div className="space-y-1">
        <h2 className="text-sm font-semibold text-destructive">
          Specialist results could not be loaded
        </h2>
        <p className="max-w-md text-xs leading-relaxed text-text-muted">
          This evaluation is complete, but the saved scorecard is temporarily
          unavailable. Try again to retrieve the findings.
        </p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className={cn(
          BUTTON_STYLES.base,
          BUTTON_STYLES.variants.secondary,
          BUTTON_STYLES.sizes.sm,
          "gap-1.5 text-xs font-semibold",
        )}
      >
        <ArrowsClockwise className="size-3.5" aria-hidden="true" />
        Try again
      </button>
    </section>
  );
}

function EmptyStorageState({ label }: { label: string }) {
  return (
    <section
      className="overflow-hidden rounded-md border border-border bg-surface"
      aria-label="Empty SLM storage"
    >
      <div className="grid min-w-0 xl:grid-cols-[minmax(0,1fr)_19rem]">
        <div className="px-5 py-10 sm:px-8 sm:py-12">
          <div className="flex items-center gap-3" aria-hidden="true">
            <span className="flex size-10 items-center justify-center rounded-sm border border-border-strong bg-surface-subtle text-primary">
              <FolderOpen className="size-5" />
            </span>
            <span className="h-px w-10 bg-border-strong" />
            <span className="flex size-10 items-center justify-center rounded-sm border border-border-strong bg-surface-subtle text-primary">
              <FileText className="size-5" />
            </span>
            <span className="h-px w-10 bg-border-strong" />
            <span className="flex size-10 items-center justify-center rounded-sm border border-border-strong bg-surface-subtle text-text-muted">
              <span className="size-2 rounded-full bg-border-strong" />
            </span>
          </div>
          <p className="mt-8 text-xs font-semibold text-primary">
            Storage first
          </p>
          <h2 className="mt-2 text-xl font-semibold leading-tight text-text sm:text-2xl">
            No SLMs ready for the {label} desk.
          </h2>
          <p className="mt-3 max-w-xl text-sm leading-relaxed text-text-muted">
            Upload a learning module to SLM Storage. Once it is processed, it
            will appear here for specialist review.
          </p>
          <Link
            to="/documents"
            className={cn(
              BUTTON_STYLES.base,
              BUTTON_STYLES.variants.primary,
              BUTTON_STYLES.sizes.sm,
              "mt-6 text-xs font-semibold",
            )}
          >
            <span>Go to SLM Storage</span>
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </Link>
        </div>
        <aside className="border-t border-border bg-surface-subtle/45 px-5 py-6 sm:px-6 xl:border-l xl:border-t-0">
          <p className="text-xs font-semibold text-text">What happens next</p>
          <ol className="mt-5 divide-y divide-border/80 border-y border-border/80 text-xs">
            <li className="flex gap-3 py-3">
              <span className="font-mono text-text-muted">01</span>
              <span className="leading-relaxed text-text-muted">
                Upload and process the SLM.
              </span>
            </li>
            <li className="flex gap-3 py-3">
              <span className="font-mono text-text-muted">02</span>
              <span className="leading-relaxed text-text-muted">
                Open the specialist desk.
              </span>
            </li>
            <li className="flex gap-3 py-3">
              <span className="font-mono text-text-muted">03</span>
              <span className="leading-relaxed text-text-muted">
                Review evidence and confirm the result.
              </span>
            </li>
          </ol>
        </aside>
      </div>
    </section>
  );
}

export function SpecialistScoreboardPage(
  props: SpecialistScoreboardPageProps = {},
) {
  const {
    validAgent,
    meta,
    routeDocId,
    allQueueItems,
    activeItem,
    activeDocument,
    activeDocId,
    latestJob,
    latestJobId,
    isCompleted,
    isEvaluating,
    isLoading,
    isLoadingResults,
    isResultsError,
    refetchResults,
    results,
    domainScore,
    showConfirmModal,
    showReviewModal,
    setShowConfirmModal,
    setShowReviewModal,
    handleModalSubmitted,
    handleReviewModalClose,
  } = useSpecialistWorkspace(props);

  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)] bg-canvas">
      <main className="mx-auto flex w-full max-w-[108rem] flex-1 flex-col space-y-7 px-4 py-6 sm:px-7 sm:py-8">
        <h1 className="sr-only">{meta.fullName} specialist workspace</h1>

        {isLoading ? (
          <SpecialistWorkspaceLoading label={meta.shortLabel} />
        ) : allQueueItems.length === 0 ? (
          <EmptyStorageState label={meta.shortLabel} />
        ) : !routeDocId ? (
          <SpecialistDirectoryView
            items={allQueueItems}
            validAgent={validAgent}
            meta={meta}
          />
        ) : (
          /* ── 2. TARGETED MODULE EVALUATION & SCORECARD: /specialists/$agentId/$documentId ───────────────── */
          <div className="space-y-4">
            {isEvaluating ? (
              /* Live Evaluating Progress State */
              <SpecialistEvaluationLoading
                label={meta.shortLabel}
                title={`${meta.fullName} Evaluation in Progress`}
                status={latestJob?.status || "EVALUATING"}
              />
            ) : isCompleted ? (
              /* Completed State: Metadata + specialist results scorecard */
              isResultsError && !results ? (
                <SpecialistResultsError onRetry={() => void refetchResults()} />
              ) : isLoadingResults || !results ? (
                <SpecialistResultsLoading />
              ) : (
                <SpecialistResultsScoreboard
                  validAgent={validAgent}
                  meta={meta}
                  activeItem={activeItem}
                  activeDocument={activeDocument}
                  latestJobId={latestJobId}
                  results={results}
                  domainScore={domainScore}
                  onOpenReviewModal={() => setShowReviewModal(true)}
                  onOpenReevaluateModal={() => setShowConfirmModal(true)}
                />
              )
            ) : (
              /* Unevaluated / READY Launchpad */
              <SpecialistLaunchpad
                activeItem={activeItem}
                activeDocument={activeDocument}
                meta={meta}
                validAgent={validAgent}
                onLaunch={() => setShowConfirmModal(true)}
              />
            )}
          </div>
        )}
      </main>

      {/* ── Confirmation / Re-evaluation Modal ────────────────────────────── */}
      {showConfirmModal && activeDocId && (
        <EvaluationConfirmModal
          documentId={activeDocId}
          documentTitle={
            activeDocument?.title || activeItem?.title || "Course Module"
          }
          detectedProgram={
            activeDocument?.program || activeItem?.program || null
          }
          targetAgent={validAgent}
          onClose={() => setShowConfirmModal(false)}
          onSubmitted={handleModalSubmitted}
        />
      )}

      {/* ── Review & Correct Scores Modal ─────────────────────────────────── */}
      {showReviewModal && latestJobId && domainScore && (
        <AgentReviewModal
          agentName={validAgent}
          evaluationId={latestJobId}
          criteria={domainScore.criteria || []}
          onClose={handleReviewModalClose}
        />
      )}
    </div>
  );
}

export default SpecialistScoreboardPage;
