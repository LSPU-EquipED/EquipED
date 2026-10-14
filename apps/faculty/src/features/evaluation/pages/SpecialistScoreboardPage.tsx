import { Link } from "@tanstack/react-router";
import { ArrowRight, FileText, FolderOpen } from "@phosphor-icons/react";
import { Skeleton } from "@equiped/ui";
import { cn } from "@equiped/ui";
import { BUTTON_STYLES } from "@equiped/ui";
import type { TargetAgent } from "@equiped/types";
import { SpecialistEvaluationFailure } from "../components/SpecialistEvaluationFailure";
import { EvaluationProgress } from "../components/EvaluationProgress";
import { EvaluationReviewDialog } from "../components/EvaluationReviewDialog";
import { EvaluationConfirmModal } from "../components/EvaluationConfirmModal";
import { SpecialistDirectoryView } from "../components/SpecialistDirectoryView";
import { SpecialistLaunchpad } from "../components/SpecialistLaunchpad";
import { EvaluationResultState } from "../components/EvaluationResultState";
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
    hasNewerRun,
    openLatestRun,
    isCompleted,
    isFailed,
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
            {hasNewerRun && (
              <div
                role="status"
                className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3 text-sm text-text-muted"
              >
                <span>
                  A newer evaluation is available. You are viewing the run you
                  opened.
                </span>
                <button
                  type="button"
                  onClick={openLatestRun}
                  className="font-semibold text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
                >
                  View latest run
                </button>
              </div>
            )}
            {isEvaluating ? (
              /* Live Evaluating Progress State */
              <EvaluationProgress
                documentTitle={activeItem?.title || activeDocument?.title}
                targetAgent={validAgent}
                status={latestJob?.status}
              />
            ) : isFailed ? (
              <SpecialistEvaluationFailure
                errorMessage={latestJob?.error_message}
                onRetry={() => setShowConfirmModal(true)}
              />
            ) : isCompleted ? (
              /* Completed State: Metadata + specialist results scorecard */
              latestJob && (
                <EvaluationResultState
                  evaluation={latestJob}
                  validAgent={validAgent}
                  meta={meta}
                  activeItem={activeItem}
                  activeDocument={activeDocument}
                  results={results}
                  domainScore={domainScore}
                  isLoading={isLoadingResults}
                  isError={isResultsError}
                  onRetry={() => void refetchResults()}
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
        <EvaluationReviewDialog
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
