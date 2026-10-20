import { useState } from "react";
import type { TargetAgent } from "@equiped/types";
import { SpecialistEvaluationFailure } from "../components/SpecialistEvaluationFailure";
import { EvaluationProgress } from "../components/EvaluationProgress";
import { EvaluationReviewDialog } from "../components/EvaluationReviewDialog";
import { EvaluationConfirmModal } from "../components/EvaluationConfirmModal";
import { SpecialistDirectoryView } from "../components/SpecialistDirectoryView";
import { SpecialistLaunchpad } from "../components/SpecialistLaunchpad";
import { EvaluationResultState } from "../components/EvaluationResultState";
import { useSpecialistWorkspace } from "../hooks/useSpecialistWorkspace";
import { useSpecialistQueue } from "../hooks/useSpecialistQueue";
import { SelectModuleModal } from "../components/SelectModuleModal";
import {
  WorkspaceLoading,
  WorkspaceRecovery,
} from "../components/workspace/WorkspaceStates";
import "../styles/specialist-workspace.css";

export interface SpecialistScoreboardPageProps {
  agentId?: TargetAgent;
  documentId?: string;
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
    isWorkspaceError,
    refetchWorkspace,
    isLoadingResults,
    isResultsError,
    refetchResults,
    results,
    assessment,
    isAssessmentPending,
    domainScore,
    showConfirmModal,
    showReviewModal,
    setShowConfirmModal,
    setShowReviewModal,
    handleModalSubmitted,
    handleReviewModalClose,
  } = useSpecialistWorkspace(props);

  const [selecting, setSelecting] = useState(false);
  const moduleOptions = useSpecialistQueue(validAgent, undefined, {
    enabled: selecting,
  });
  return (
    <div className="swp">
      <main className="swp-content">
        {isLoading ? (
          <WorkspaceLoading label={`${meta.shortLabel} specialist workspace`} />
        ) : isWorkspaceError ? (
          <WorkspaceRecovery
            kind="workspace"
            onRetry={() => void refetchWorkspace()}
          />
        ) : !routeDocId ? (
          <SpecialistDirectoryView
            items={allQueueItems}
            validAgent={validAgent}
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
            ) : isFailed && !assessment ? (
              <SpecialistEvaluationFailure
                key={latestJobId || activeDocId}
                documentTitle={activeItem?.title || activeDocument?.title}
                errorMessage={latestJob?.error_message}
                onRetry={() => setShowConfirmModal(true)}
              />
            ) : isCompleted || assessment ? (
              /* Completed State: Metadata + specialist results scorecard */
              latestJob && (
                <EvaluationResultState
                  evaluation={latestJob}
                  validAgent={validAgent}
                  meta={meta}
                  activeItem={activeItem}
                  activeDocument={activeDocument}
                  results={results}
                  assessment={assessment}
                  isAssessmentPending={isAssessmentPending}
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
              activeItem && (
                <SpecialistLaunchpad
                  key={`${validAgent}:${activeDocId}`}
                  activeItem={activeItem}
                  activeDocument={activeDocument}
                  validAgent={validAgent}
                  onSubmitted={handleModalSubmitted}
                  onSelect={() => setSelecting(true)}
                />
              )
            )}
          </div>
        )}
      </main>

      {selecting && (
        <SelectModuleModal
          agentId={validAgent}
          items={moduleOptions.data?.items || []}
          isLoading={moduleOptions.isLoading}
          isError={moduleOptions.isError && !moduleOptions.data}
          onRetry={() => void moduleOptions.refetch()}
          onClose={() => setSelecting(false)}
        />
      )}
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
