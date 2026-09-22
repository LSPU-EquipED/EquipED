import {
  ArrowsClockwise,
  BookOpen,
  CaretRight,
  CheckCircle,
  FileText,
  Lightbulb,
  Scales,
  ShieldCheck,
  WarningCircle,
} from "@phosphor-icons/react";
import { Badge } from "@equiped/ui";
import { Button } from "@equiped/ui";
import { cn } from "@equiped/ui";
import { Skeleton } from "@equiped/ui";
import { TYPOGRAPHY } from "@equiped/ui";
import { isTargetAgent, TARGET_AGENT_META, type TargetAgent } from "@equiped/types";
import { useScorecardController } from "../hooks/useScorecardController";
import {
  formatScore,
  cleanJustification,
  overallScoreDisplay,
  monitoringPercentage,
  agentShortLabel,
  getAdjectivalRatingClasses,
} from "../utils/scoreHelpers";
import { ScorecardPdfExport } from "./ScorecardPdfExport";
import { AgentReviewModal } from "./AgentReviewModal";
import { SpecialistExportDownloadButton } from "./ExportDocument";
import { EvaluationConfirmModal } from "./EvaluationConfirmModal";
import {
  EvaluationResultsScoreboard,
  EvaluationResultsSkeleton,
} from "./EvaluationResultsScoreboard";

function formatDuration(seconds?: number | null): string {
  if (seconds == null) return "";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

const DOMAIN_ICONS: Record<string, typeof Lightbulb> = {
  sme: Lightbulb,
  coordinator: BookOpen,
  gad: Scales,
  itso: ShieldCheck,
};



function EvaluationProgressSkeleton({
  title,
  status,
}: {
  title: string;
  status: string;
}) {
  return (
    <section
      className="overflow-hidden rounded-md border border-info/30 bg-surface"
      role="status"
      aria-label="Evaluation in progress"
      aria-busy="true"
    >
      <div className="grid gap-6 p-6 sm:p-8 lg:grid-cols-[minmax(0,1fr)_18rem] lg:p-10">
        <div className="space-y-5">
          <div className="flex items-center gap-3">
            <Skeleton className="size-9 rounded-sm" />
            <div className="space-y-2">
              <Skeleton className="h-2.5 w-28" />
              <Skeleton className="h-3.5 w-44" />
            </div>
          </div>
          <h2 className="text-base font-semibold text-text">{title}</h2>
          <Skeleton className="h-3 w-full max-w-xl" />
          <Skeleton className="h-3 w-4/5 max-w-lg" />
          <div className="flex items-center gap-3 border-y border-border py-4">
            <Skeleton className="h-8 w-24" />
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-8 w-20" />
          </div>
        </div>
        <aside className="border-t border-border bg-surface-subtle/45 pt-6 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
          <Skeleton className="h-2.5 w-24" />
          <Skeleton className="mt-3 h-4 w-36" />
          <div className="mt-6 space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={index}
                className="flex items-center gap-3 border-b border-border pb-3"
              >
                <Skeleton className="size-7 rounded-sm" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-2.5 w-24" />
                  <Skeleton className="h-1 w-full" />
                </div>
              </div>
            ))}
          </div>
        </aside>
      </div>
      <div className="flex items-center justify-between border-t border-border bg-surface-subtle/35 px-5 py-3 text-xs text-text-muted sm:px-6">
        <span>Status: {status}</span>
        <span>Updating automatically</span>
      </div>
      <span className="sr-only">
        Evaluation is running. Loading current findings.
      </span>
    </section>
  );
}


function EvaluationResultsError({ onRetry }: { onRetry: () => void }) {
  return (
    <section
      className="flex min-h-56 flex-col items-center justify-center gap-3 border border-destructive/30 bg-destructive-soft px-6 py-10 text-center"
      role="alert"
    >
      <WarningCircle className="size-6 text-destructive" aria-hidden="true" />
      <div className="space-y-1">
        <h2 className="text-sm font-semibold text-destructive">
          Results could not be loaded
        </h2>
        <p className="max-w-md text-xs leading-relaxed text-text-muted">
          The evaluation is complete, but its scorecard is temporarily
          unavailable. Try again to retrieve the saved findings.
        </p>
      </div>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={onRetry}
        className="gap-1.5 text-xs font-semibold"
      >
        <ArrowsClockwise className="size-3.5" aria-hidden="true" />
        Try again
      </Button>
    </section>
  );
}

export function Scorecard() {
  const {
    id,
    evaluation,
    isLoading,
    isError,
    results,
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
        <EvaluationResultsSkeleton />
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

  const ActiveDomainIcon = DOMAIN_ICONS[effectiveDomainId] || FileText;
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
            <EvaluationProgressSkeleton
              title={`${singleAgentMeta.fullName} Evaluation in Progress`}
              status={evaluation.status}
            />
          ) : isFailed ? (
            <div className="rounded-md border border-destructive/30 bg-destructive-soft p-8 text-center space-y-2">
              <WarningCircle
                className="size-6 text-destructive mx-auto"
                aria-hidden="true"
              />
              <h2 className="text-sm font-bold text-destructive">
                Evaluation Failed
              </h2>
              <p className="text-xs text-text-muted max-w-md mx-auto">
                {evaluation.error_message ||
                  "The evaluation job failed to complete. Please try submitting again."}
              </p>
            </div>
          ) : (
            <EvaluationResultsScoreboard
              evaluation={evaluation}
              results={results}
              singleAgentMeta={singleAgentMeta}
              activeDomainData={activeDomainData}
              effectiveDomainId={effectiveDomainId}
              sortedCriteria={sortedCriteria}
              isLoadingResults={isLoadingResults}
              isResultsError={isResultsError && !results}
              onRetryResults={() => void refetchResults()}
              onOpenReview={() => handleOpenReview(effectiveDomainId)}
              onOpenReevaluate={handleOpenReevaluate}
            />
          )}
        </main>
      ) : (
        /* 2-Column Side-by-Side Assessment Workspace (Historical 4-Agent Bundles) */
        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[22rem_minmax(0,1fr)] xl:grid-cols-[26rem_minmax(0,1fr)]">
          <aside
            aria-label="Executive Dossier & Review Domains"
            className="flex flex-col h-full min-h-0 border-r border-border bg-surface overflow-y-auto p-4 sm:p-5 space-y-4"
          >
            <div className="border-b border-border pb-3">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                Evaluation results
              </p>
              <h2 className="mt-1 break-words text-sm font-semibold leading-snug text-text">
                {results?.document_title || evaluation.document_id}
              </h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {results && activeDomainData ? (
                  <SpecialistExportDownloadButton
                    domainData={{
                      agentId: effectiveDomainId,
                      documentTitle: results.document_title || evaluation.document_id,
                      program: results.program ?? null,
                      evaluationId: evaluation.evaluation_id,
                      isPartial: results.is_partial,
                      partialReason: results.partial_reason,
                      evaluationStatus: results.evaluation_status,
                      subtotal: activeDomainData.subtotal,
                      max_score: activeDomainData.max_score || 4,
                      status: activeDomainData.status,
                      adjectival_rating: activeDomainData.adjectival_rating ?? undefined,
                      criteria: activeDomainData.criteria || [],
                      summary: activeDomainData.summary,
                      version: activeDomainData.version,
                      form_snapshot_id: activeDomainData.form_snapshot_id,
                      results,
                    }}
                  />
                ) : null}
                {results && isTerminal ? <ScorecardPdfExport results={results} /> : null}
              </div>
            </div>
            {/* Overall Verdict Card */}
            {results ? (
              availableDomains.length < 4 &&
              isTargetAgent(evaluation.target_agent) ? (
                <div className="rounded-md border border-border bg-surface-subtle p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
                      Accreditation Progress
                    </span>
                    <Badge variant="info">In Progress</Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-text tabular-nums">
                      {availableDomains.length} / 4 Domains Evaluated
                    </span>
                  </div>
                  <span className="text-[11px] text-text-muted block">
                    Composite score finalizes once all 4 specialist domains are
                    evaluated.
                  </span>
                </div>
              ) : (
                (() => {
                  const display = overallScoreDisplay({
                    overallScore: results.overall_score,
                    synthesizedScore: results.synthesized_score,
                  });
                  return (
                    <div className="rounded-md border border-border bg-surface-subtle p-4 space-y-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
                        Overall Assessment Verdict
                      </span>
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            "inline-flex items-center rounded-xs px-2.5 py-1 text-xs font-bold uppercase tracking-wider",
                            getAdjectivalRatingClasses(
                              results.adjectival_rating ?? undefined,
                            ),
                          )}
                        >
                          {results.adjectival_rating}
                        </span>
                        <span className="text-sm font-bold text-text tabular-nums">
                          ★ {display.canonicalText}
                        </span>
                      </div>
                      <span className="text-[11px] text-text-muted tabular-nums block">
                        {display.monitoringText} monitoring percentage
                      </span>
                    </div>
                  );
                })()
              )
            ) : null}

            {/* Legacy notice */}
            {results?.legacy_notice && (
              <div className="rounded-sm border border-border bg-surface-subtle p-3 text-xs text-text-muted leading-relaxed font-medium">
                {results.legacy_notice}
              </div>
            )}

            {/* Partial Notice */}
            {isPartial && !isTargetAgent(evaluation.target_agent) && (
              <div className="rounded-sm border border-warning/30 bg-warning-soft p-3 text-xs text-warning leading-relaxed">
                <strong>Partial Review: </strong>
                {partialReason ||
                  "This evaluation ran without a curriculum reference. Coordinator review was skipped."}
              </div>
            )}

            {/* 4-Domain Navigation Matrix */}
            <div className="space-y-2 pt-1">
              <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted block px-1">
                Review Domains ({domainKeys.length})
              </span>

              <div
                className="space-y-1.5"
                role="tablist"
                aria-label="Review domain selection"
              >
                {domainKeys.map((domain) => {
                  const Icon = DOMAIN_ICONS[domain] || FileText;
                  const domainData = results?.domain_scores[domain];
                  const isSkipped =
                    isPartial && domain === "coordinator" && !domainData;
                  const isSelected = domain === effectiveDomainId;
                  const percent = domainData
                    ? monitoringPercentage(
                        domainData.subtotal,
                        domainData.max_score || 4,
                      )
                    : 0;

                  if (isSkipped) {
                    return (
                      <div
                        key={`${domain}-nav-skipped`}
                        className="rounded-sm border border-border bg-surface-subtle/50 p-3 flex items-center justify-between text-xs opacity-70"
                      >
                        <div className="flex items-center gap-2">
                          <Icon
                            className="size-4 text-text-muted"
                            aria-hidden="true"
                          />
                          <span className="font-semibold text-text-muted">
                            {TARGET_AGENT_META[domain as TargetAgent]?.shortLabel ?? agentShortLabel(domain) ?? domain}
                          </span>
                        </div>
                        <Badge variant="warning">Skipped</Badge>
                      </div>
                    );
                  }

                  if (!domainData) {
                    return (
                      <div
                        key={`${domain}-nav-pending`}
                        className="rounded-sm border border-dashed border-border bg-surface-subtle/30 p-3 flex items-center justify-between text-xs"
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className="flex size-7 items-center justify-center rounded-xs shrink-0 bg-surface text-text-muted border border-border">
                            <Icon className="size-4" aria-hidden="true" />
                          </div>
                          <div className="min-w-0">
                            <span className="font-semibold text-text-muted block truncate">
                              {TARGET_AGENT_META[domain as TargetAgent]?.shortLabel ?? agentShortLabel(domain) ?? domain}
                            </span>
                            <span className="text-[10px] text-text-muted font-mono">
                              Not evaluated
                            </span>
                          </div>
                        </div>
                        <Badge variant="neutral">Pending</Badge>
                      </div>
                    );
                  }
                  return (
                    <button
                      key={domain}
                      type="button"
                      role="tab"
                      aria-selected={isSelected}
                      onClick={() => setSelectedDomainId(domain)}
                      className={cn(
                        "w-full text-left p-3 rounded-sm border transition-all flex items-start justify-between gap-3 cursor-pointer select-none",
                        isSelected
                          ? "border-primary bg-primary-soft/50 text-primary shadow-xs ring-1 ring-primary/20"
                          : "border-border bg-surface hover:bg-surface-subtle hover:border-border-strong text-text",
                      )}
                    >
                      <div className="flex items-start gap-2.5 min-w-0">
                        <div
                          className={cn(
                            "flex size-7 items-center justify-center rounded-xs shrink-0 mt-0.5 border",
                            isSelected
                              ? "bg-primary-soft text-primary border-primary/30"
                              : "bg-surface-subtle text-text-muted border-border",
                          )}
                        >
                          <Icon className="size-4" aria-hidden="true" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-xs truncate">
                              {TARGET_AGENT_META[domain as TargetAgent]?.shortLabel ?? agentShortLabel(domain) ?? domain}
                            </span>
                            {domainData.version != null ? (
                              <Badge variant="neutral">
                                Rev {domainData.version}
                              </Badge>
                            ) : null}
                          </div>
                          <span className="text-[11px] text-text-muted block mt-0.5 tabular-nums">
                            {formatScore(domainData.subtotal)} /{" "}
                            {formatScore(domainData.max_score || 4)} ({percent}
                            %)
                          </span>
                        </div>
                      </div>

                      <CaretRight
                        className={cn(
                          "size-4 shrink-0 transition-transform mt-1.5",
                          isSelected ? "text-primary" : "text-text-muted",
                        )}
                      />
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Audit Timing & Metadata */}
            <div className="border-t border-border pt-3 space-y-1.5 text-[11px] text-text-muted font-medium">
              <div className="flex items-center justify-between">
                <span>Submitted:</span>
                <strong className="text-text tabular-nums">
                  {new Date(evaluation.submitted_at).toLocaleDateString()}
                </strong>
              </div>
              {evaluation.completed_at ? (
                <div className="flex items-center justify-between">
                  <span>Completed:</span>
                  <strong className="text-text tabular-nums">
                    {new Date(evaluation.completed_at).toLocaleDateString()}
                  </strong>
                </div>
              ) : null}
              {results?.duration_seconds != null ? (
                <div className="flex items-center justify-between">
                  <span>Duration:</span>
                  <strong className="text-text tabular-nums">
                    {formatDuration(results.duration_seconds)}
                  </strong>
                </div>
              ) : null}
            </div>
          </aside>

          {/* RIGHT COLUMN: Active Domain Criteria & Quoted Evidence (~62% width) */}
          <main
            aria-label="Domain Criteria & Findings"
            className="flex flex-col h-full min-h-0 overflow-y-auto bg-canvas p-4 sm:p-6 md:p-8 space-y-5"
          >
            {isEvaluating ? (
              <EvaluationProgressSkeleton
                title="Multi-Agent Evaluation in Progress"
                status={evaluation.status}
              />
            ) : isFailed ? (
              <div className="rounded-md border border-destructive/30 bg-destructive-soft p-8 text-center space-y-2">
                <WarningCircle
                  className="size-6 text-destructive mx-auto"
                  aria-hidden="true"
                />
                <h2 className="text-sm font-bold text-destructive">
                  Evaluation Failed
                </h2>
                <p className="text-xs text-text-muted max-w-md mx-auto">
                  {evaluation.error_message ||
                    "The evaluation job failed to complete."}
                </p>
              </div>
            ) : isResultsError && !results ? (
              <EvaluationResultsError onRetry={() => void refetchResults()} />
            ) : isLoadingResults ? (
              <EvaluationResultsSkeleton />
            ) : activeDomainData ? (
              <div className="space-y-5">
                {/* Active Domain Header Bar */}
                <div className="rounded-md border border-border bg-surface p-5 sm:p-6 flex flex-wrap items-center justify-between gap-4 shadow-none">
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div className="flex size-9 items-center justify-center rounded-xs bg-primary-soft text-primary border border-primary/20 shrink-0">
                      <ActiveDomainIcon className="size-5" aria-hidden="true" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className={TYPOGRAPHY.headingSm}>
                          {agentLabels[effectiveDomainId] ||
                            effectiveDomainId.toUpperCase()}
                        </h2>
                        {activeDomainData.version != null ? (
                          <Badge variant="neutral">
                            Revision {activeDomainData.version}
                          </Badge>
                        ) : null}
                        {activeDomainData.version == null &&
                          (results?.legacy_notice ||
                            activeDomainData.form_snapshot_id == null) &&
                          results && (
                            <Badge variant="neutral">
                              Legacy — form snapshot unavailable
                            </Badge>
                          )}
                      </div>
                      <p className="text-xs text-text-muted mt-0.5">
                        {activeDomainData.summary ||
                          "Domain review criteria evaluated against institutional quality standards."}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs font-bold text-text tabular-nums">
                      Subtotal: {formatScore(activeDomainData.subtotal)} /{" "}
                      {formatScore(activeDomainData.max_score || 4)}
                    </span>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => handleOpenReview(effectiveDomainId)}
                      className="text-xs h-7.5 px-2.5"
                    >
                      Review Scores
                    </Button>
                  </div>
                </div>

                {/* Criteria Table */}
                <div className="rounded-md border border-border bg-surface overflow-hidden shadow-none">
                  <div className="divide-y divide-border bg-surface">
                    {sortedCriteria.map((criterion, idx) => {
                      const isUngrounded = Boolean(criterion.is_ungrounded);
                      const isPassing = criterion.score >= 3.0;

                      return (
                        <div
                          key={`${effectiveDomainId}-${criterion.criterion_id || idx}`}
                          className="p-4 sm:p-5 space-y-2.5 hover:bg-surface-subtle/30 transition-colors"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="flex items-start gap-2.5 min-w-0 flex-1">
                              <span className="font-mono text-xs font-bold text-text-muted shrink-0 whitespace-nowrap bg-surface-subtle border border-border px-1.5 py-0.5 rounded-xs mt-0.5">
                                {criterion.criterion_id}
                              </span>
                              <div className="min-w-0">
                                <span className="font-semibold text-text text-sm block leading-snug">
                                  {criterion.criterion_text}
                                </span>
                                {criterion.description ? (
                                  <p className="text-xs text-text-muted mt-1 leading-relaxed">
                                    {criterion.description}
                                  </p>
                                ) : null}
                              </div>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              {isUngrounded ? (
                                <Badge variant="warning">Ungrounded</Badge>
                              ) : null}
                              <span
                                className={cn(
                                  "inline-flex items-center rounded-xs px-2.5 py-0.5 text-xs font-bold tabular-nums border",
                                  isPassing
                                    ? "bg-success-soft text-success border-success/30"
                                    : "bg-warning-soft text-warning border-warning/30",
                                )}
                              >
                                Score {formatScore(criterion.score)} / 4
                              </span>
                            </div>
                          </div>

                          {/* Quoted Evidence & Findings Callout */}
                          {criterion.justification || criterion.evidence ? (
                            <div className="rounded-sm border border-warning/30 bg-warning-soft/15 p-3.5 space-y-1.5 text-xs">
                              {criterion.evidence ? (
                                <div className="font-mono text-text bg-surface/80 p-2.5 border border-border rounded-xs">
                                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block mb-0.5">
                                    Quoted Evidence:
                                  </span>
                                  "{cleanJustification(criterion.evidence)}"
                                </div>
                              ) : null}
                              {criterion.justification ? (
                                <p className="text-text-muted leading-relaxed">
                                  <strong>Specialist Finding: </strong>
                                  {cleanJustification(criterion.justification)}
                                </p>
                              ) : null}
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 text-xs text-success font-medium pt-0.5">
                              <CheckCircle
                                className="size-3.5 text-success shrink-0"
                                aria-hidden="true"
                              />
                              <span>
                                Verified compliant with institutional quality
                                standards.
                              </span>
                            </div>
                          )}
                          {/* Reviewer Correction Callout if Present */}
                          {criterion.reviewer_correction ? (
                            <div className="rounded-sm border border-info/30 bg-info-soft/20 p-3 text-xs space-y-1">
                              <span className="font-bold text-info block text-[10px] uppercase">
                                {criterion.reviewer_correction.action ===
                                "REJECT"
                                  ? "Authoritative CID Human Override Flagged (Rejected)"
                                  : "Authoritative CID Human Override Applied"}
                              </span>
                              {criterion.reviewer_correction.score != null ? (
                                <p className="text-text font-medium">
                                  Override Score:{" "}
                                  {criterion.reviewer_correction.score} / 4
                                </p>
                              ) : null}
                              {criterion.reviewer_correction.justification ? (
                                <p className="text-text-muted leading-relaxed">
                                  <strong>Reviewer Justification: </strong>
                                  {cleanJustification(
                                    criterion.reviewer_correction.justification,
                                  )}
                                </p>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Authoritative Human Review & Sign-Off */}
                <div className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-3">
                  <div className="border-b border-border pb-2.5">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-text">
                      Authoritative Faculty Review & Sign-Off
                    </h3>
                    <p className="text-xs text-text-muted mt-0.5">
                      Automated multi-agent evaluation findings are advisory.
                      CID faculty evaluators maintain final authoritative
                      determination.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-2 text-xs">
                    <div className="border-t border-border pt-1.5 text-text font-medium">
                      CID Evaluator / Reviewer Signature
                    </div>
                    <div className="border-t border-border pt-1.5 text-text font-medium">
                      Date Completed & Verified
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex h-full min-h-[20rem] items-center justify-center p-8 text-center text-text-muted">
                Select a domain on the left to inspect criteria.
              </div>
            )}
          </main>
        </div>
      )}
      {/* Review Scores Modal */}
      {reviewModalAgent && id && (
        <AgentReviewModal
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
          documentTitle={results?.document_title || evaluation.document_id}
          detectedProgram={results?.program ?? null}
          targetAgent={evaluation.target_agent}
          onClose={handleCloseReevaluate}
          onSubmitted={handleReevaluateSubmitted}
        />
      )}
    </section>
  );
}
