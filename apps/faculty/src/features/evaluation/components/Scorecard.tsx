import { SpecialistEvaluationFailure } from "./SpecialistEvaluationFailure";
import { WarningCircle } from "@phosphor-icons/react";
import { isTargetAgent } from "@equiped/types";
import { useScorecardController } from "../hooks/useScorecardController";
import { EvaluationProgress } from "./EvaluationProgress";
import { EvaluationReviewDialog } from "./EvaluationReviewDialog";
import { EvaluationConfirmModal } from "./EvaluationConfirmModal";
import {
  EvaluationResultsLoading,
  EvaluationResultState,
} from "./EvaluationResultState";
import { LegacyEvaluationResults } from "./LegacyEvaluationResults";

export function Scorecard() {
  const {
    id,
    evaluation,
    activeDocument,
    newerEvaluationId,
    isLoading,
    isError,
    results,
    assessment,
    isAssessmentPending,
    isLoadingResults,
    isResultsError,
    refetchResults,
    isTerminal,
    isFailed,
    isEvaluating,
    isPartial,
    partialReason,
    agentLabels,
    domainKeys,
    availableDomains,
    setSelectedDomainId,
    singleAgentMeta,
    isSingleAgentRun,
    effectiveDomainId,
    activeDomainData,
    sortedCriteria,
    reviewModalAgent,
    showReevaluateModal,
    handleOpenReview,
    handleCloseReview,
    handleOpenReevaluate,
    handleCloseReevaluate,
    handleReevaluateSubmitted,
  } = useScorecardController();

  if (!id) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-text-muted">
        No evaluation ID provided.
      </div>
    );
  }

  if (isLoading) {
    return (
      <main
        aria-label="Specialist Evaluation Dossier"
        className="mx-auto w-full max-w-[108rem] flex-1 space-y-4 p-4 sm:px-6 sm:py-5"
      >
        <EvaluationResultsLoading />
      </main>
    );
  }

  if (isError || !evaluation) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-canvas">
        <div className="flex flex-col items-center gap-3 text-destructive border border-destructive/30 bg-destructive-soft p-8 rounded-md max-w-md text-center">
          <WarningCircle
            className="size-8 text-destructive"
            aria-hidden="true"
          />
          <p className="text-sm font-bold">
            Failed to load evaluation details.
          </p>
        </div>
      </div>
    );
  }

  return (
    <section className="flex min-h-[calc(100dvh-3.5rem)] flex-col bg-canvas">
      <h1 className="sr-only">Evaluation results</h1>
      {isSingleAgentRun && singleAgentMeta ? (
        /* Single-Agent Evaluation Results */
        <main
          aria-label="Specialist Evaluation Dossier"
          className="mx-auto w-full max-w-[108rem] flex-1 space-y-4 p-4 sm:px-6 sm:py-5"
        >
          {isEvaluating ? (
            <EvaluationProgress
              targetAgent={singleAgentMeta.id}
              status={evaluation.status}
            />
          ) : isFailed && !assessment ? (
            <SpecialistEvaluationFailure
              errorMessage={evaluation.error_message}
              onRetry={handleOpenReevaluate}
            />
          ) : (
            <EvaluationResultState
              evaluation={evaluation}
              results={results}
              assessment={assessment}
              isAssessmentPending={isAssessmentPending}
              meta={singleAgentMeta}
              validAgent={singleAgentMeta.id}
              domainScore={activeDomainData}
              activeItem={null}
              activeDocument={activeDocument}
              context="history"
              newerEvaluationId={newerEvaluationId}
              isLoading={isLoadingResults}
              isError={isResultsError}
              onRetry={() => void refetchResults()}
              onOpenReviewModal={() => handleOpenReview(effectiveDomainId)}
              onOpenReevaluateModal={handleOpenReevaluate}
            />
          )}
        </main>
      ) : (
        <LegacyEvaluationResults
          evaluation={evaluation}
          results={results}
          isTerminal={isTerminal}
          activeDomainData={activeDomainData}
          effectiveDomainId={effectiveDomainId}
          isEvaluating={isEvaluating}
          isFailed={isFailed}
          isResultsError={isResultsError}
          isLoadingResults={isLoadingResults}
          refetchResults={refetchResults}
          isPartial={isPartial}
          partialReason={partialReason}
          availableDomains={availableDomains}
          domainKeys={domainKeys}
          agentLabels={agentLabels}
          setSelectedDomainId={setSelectedDomainId}
          sortedCriteria={sortedCriteria}
          handleOpenReview={handleOpenReview}
        />
      )}
      {/* Review Scores Modal */}
      {reviewModalAgent && id && (
        <EvaluationReviewDialog
          agentName={reviewModalAgent}
          evaluationId={id}
          criteria={results?.domain_scores[reviewModalAgent]?.criteria || []}
          onClose={handleCloseReview}
        />
      )}
      {/* Re-evaluate Confirmation Modal */}
      {showReevaluateModal && isTargetAgent(evaluation.target_agent) && (
        <EvaluationConfirmModal
          documentId={evaluation.document_id}
          documentTitle={
            results?.document_title || activeDocument?.title || "Course module"
          }
          detectedProgram={results?.program || activeDocument?.program || null}
          targetAgent={evaluation.target_agent}
          onClose={handleCloseReevaluate}
          onSubmitted={handleReevaluateSubmitted}
        />
      )}
    </section>
  );
}
