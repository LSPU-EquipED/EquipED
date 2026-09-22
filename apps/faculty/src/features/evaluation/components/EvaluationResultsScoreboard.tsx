import type { TargetAgentMeta } from "@equiped/types";
import type {
  CriterionScoreItem,
  DomainScoreBlock,
  EvaluationResponse,
  EvaluationResultsResponse,
} from "../types";
import { Button, cn, Skeleton } from "@equiped/ui";
import {
  ArrowsClockwise,
  CaretDown,
  ChartBar,
  CheckCircle,
  NotePencil,
  WarningCircle,
} from "@phosphor-icons/react";
import { SpecialistExportDownloadButton, type ExportAgentId } from "./ExportDocument";
import {
  cleanJustification,
  formatEvidenceText,
  formatScore,
  monitoringPercentage,
  getAdjectivalRatingClasses,
} from "../utils/scoreHelpers";
import { formatDateWithFallback } from "../utils/dateFormatting";
import { calculateScoreboardMetrics } from "../utils/scoreboardMetrics";

export interface EvaluationResultsScoreboardProps {
  evaluation: EvaluationResponse;
  results?: EvaluationResultsResponse;
  singleAgentMeta: TargetAgentMeta;
  activeDomainData: DomainScoreBlock | undefined;
  effectiveDomainId: string;
  sortedCriteria: CriterionScoreItem[];
  isLoadingResults: boolean;
  isResultsError: boolean;
  onRetryResults: () => void;
  onOpenReview: () => void;
  onOpenReevaluate: () => void;
}

export function EvaluationResultsSkeleton() {
  return (
    <section
      className="overflow-hidden rounded-md border border-border bg-surface"
      role="status"
      aria-label="Loading evaluation score breakdown"
      aria-busy="true"
    >
      <div className="border-b border-border px-5 py-4 sm:px-6">
        <Skeleton className="h-2.5 w-28" />
        <Skeleton className="mt-2 h-5 w-56 max-w-full" />
      </div>
      <div className="space-y-5 p-5 sm:p-7">
        <div className="grid gap-3 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="space-y-3 border border-border p-4">
              <Skeleton className="h-2.5 w-24" />
              <Skeleton className="h-7 w-16" />
            </div>
          ))}
        </div>
        <Skeleton className="h-3 w-44" />
        {Array.from({ length: 5 }).map((_, index) => (
          <div
            key={index}
            className="flex items-center gap-3 border-y border-border py-4"
          >
            <Skeleton className="size-7 rounded-sm" />
            <Skeleton className="h-3 flex-1" />
            <Skeleton className="h-6 w-12" />
          </div>
        ))}
      </div>
      <span className="sr-only">Loading evaluation score breakdown.</span>
    </section>
  );
}

export function EvaluationResultsScoreboard({
  evaluation,
  results,
  singleAgentMeta,
  activeDomainData,
  effectiveDomainId,
  sortedCriteria,
  isLoadingResults,
  isResultsError,
  onRetryResults,
  onOpenReview,
  onOpenReevaluate,
}: EvaluationResultsScoreboardProps) {
  if (isResultsError) {
    return (
      <div className="w-full">
        <section
          className="rounded-md border border-destructive/25 bg-destructive-soft p-8 text-center space-y-2"
          role="alert"
        >
          <WarningCircle className="mx-auto size-6 text-destructive" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-destructive">
            Results could not be loaded
          </h2>
          <p className="mx-auto max-w-lg text-xs leading-relaxed text-text-muted">
            The evaluation is complete, but its saved scorecard is temporarily unavailable.
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onRetryResults}
            className="mt-3 gap-1.5 text-xs font-semibold"
          >
            <ArrowsClockwise className="size-3.5" aria-hidden="true" />
            Try again
          </Button>
        </section>
      </div>
    );
  }

  if (isLoadingResults) {
    return <EvaluationResultsSkeleton />;
  }

  if (!activeDomainData) {
    return (
      <div className="w-full">
        <section className="rounded-md border border-border bg-surface p-8 text-center text-xs text-text-muted">
          No criteria recorded for this evaluation.
        </section>
      </div>
    );
  }

  const displayCriteria = sortedCriteria;

  const maxScore = activeDomainData.max_score || 4;
  const score = activeDomainData.subtotal;
  const compliance = monitoringPercentage(score, maxScore);
  const evidenceCount = displayCriteria.filter((criterion) => criterion.evidence).length;
  const reviewCount = displayCriteria.filter((criterion) => criterion.reviewer_correction).length;
  const displayTitle = results?.document_title || evaluation.document_id;
  const referenceBasis = singleAgentMeta.requiresCurriculum
    ? "Institutional curriculum"
    : "Specialist rubric";

  const { attentionCount, strongCount, scoreBuckets, scoreBucketMax } =
    calculateScoreboardMetrics(displayCriteria);

  const exportDomainData =
    results && activeDomainData
      ? {
          agentId: effectiveDomainId,
          documentTitle: displayTitle,
          program: results.program ?? null,
          evaluationId: evaluation.evaluation_id,
          isPartial: results.is_partial,
          partialReason: results.partial_reason,
          evaluationStatus: results.evaluation_status,
          subtotal: activeDomainData.subtotal,
          max_score: maxScore,
          status: activeDomainData.status,
          adjectival_rating: activeDomainData.adjectival_rating ?? undefined,
          criteria: activeDomainData.criteria || [],
          summary: activeDomainData.summary,
          version: activeDomainData.version,
          form_snapshot_id: activeDomainData.form_snapshot_id,
          results,
        }
      : null;

  return (
    <div className="w-full rounded-md border border-border bg-surface overflow-hidden shadow-none">
      {/* Integrated Institutional Workbench Grid:
          Structured with hairline borders (divide-x) instead of disconnected floating cards */}
      <div className="grid min-w-0 lg:grid-cols-[20rem_minmax(0,1fr)] xl:grid-cols-[22rem_minmax(0,1fr)] divide-y lg:divide-y-0 lg:divide-x divide-border">
        {/* LEFT COLUMN: Overview / Score Dossier, Module Details & Governance */}
        <aside className="min-w-0 divide-y divide-border bg-surface-subtle/45" aria-label="Evaluation overview">
          {/* 1. Score Dossier & Actions Pane */}
          <div className="p-4 sm:p-5 space-y-4">
            <div className="space-y-0.5">
              <h2 className="break-words text-base font-semibold leading-snug text-text [overflow-wrap:anywhere]">
                {singleAgentMeta.shortLabel} Unit performance score
              </h2>
              <p className="text-xs text-text-muted [overflow-wrap:anywhere] truncate" title={displayTitle}>
                {displayTitle}
              </p>
            </div>

            {/* Score & Profile Block */}
            <div className="space-y-3 border-t border-border pt-3">
              <div className="flex items-baseline justify-between gap-2">
                <div className="flex items-baseline gap-1.5">
                  <span className="text-2xl font-semibold tracking-tight text-text tabular-nums">
                    {formatScore(score)}
                  </span>
                  <span className="text-xs text-text-muted tabular-nums">
                    / {formatScore(maxScore)}
                  </span>
                </div>
                {activeDomainData.adjectival_rating ? (
                  <span
                    className={cn(
                      "rounded-xs border px-2 py-0.5 text-xs font-medium",
                      getAdjectivalRatingClasses(activeDomainData.adjectival_rating),
                    )}
                  >
                    {activeDomainData.adjectival_rating}
                  </span>
                ) : null}
              </div>

              {/* Compliance Bar */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs text-text-muted">
                  <span>Accreditation compliance</span>
                  <span className="font-medium text-text tabular-nums">{compliance}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-xs bg-surface-subtle" aria-hidden="true">
                  <div
                    className="h-full rounded-xs bg-primary transition-[width]"
                    style={{ width: `${Math.min(100, Math.max(0, compliance))}%` }}
                  />
                </div>
              </div>

              {/* Criteria Summary Metrics */}
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs tabular-nums text-text-muted">
                <span>{sortedCriteria.length} criteria · {strongCount} strong</span>
                {attentionCount > 0 && (
                  <span className="inline-flex items-center gap-1 font-medium text-warning">
                    <WarningCircle className="size-3.5" aria-hidden="true" />
                    {attentionCount} need attention
                  </span>
                )}
              </div>

              {/* Score Profile Mini Distribution Chart */}
              <div className="border-t border-border/60 pt-2.5" aria-label="Score profile">
                <div className="flex items-center gap-1.5 text-xs font-medium text-text-muted">
                  <ChartBar className="size-3.5 text-primary" aria-hidden="true" />
                  Score profile
                </div>
                <div
                  className="mt-2 flex h-10 items-end gap-2"
                  role="img"
                  aria-label="Criteria score distribution from 4 to 1"
                >
                  {scoreBuckets.map(({ bucket, count }) => {
                    const height =
                      count === 0 ? 8 : Math.max(22, (count / scoreBucketMax) * 100);
                    const barColor =
                      bucket >= 4
                        ? "bg-success"
                        : bucket === 3
                          ? "bg-primary"
                          : bucket === 2
                            ? "bg-warning"
                            : "bg-destructive";
                    return (
                      <div
                        key={bucket}
                        className="flex min-w-0 flex-1 flex-col items-center gap-1"
                      >
                        <div
                          className="flex h-7 w-full items-end rounded-xs bg-surface-subtle px-0.5"
                          aria-hidden="true"
                        >
                          <span
                            className={cn("block w-full rounded-xs", barColor)}
                            style={{ height: `${height}%` }}
                          />
                        </div>
                        <span className="text-[10px] tabular-nums text-text-muted">
                          {bucket}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Action Buttons: Unified, Full-Width, Clear Hierarchy */}
            <div className="space-y-2 border-t border-border pt-3">
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={onOpenReview}
                className="w-full justify-center gap-1.5 text-xs font-semibold h-8.5"
              >
                <NotePencil className="size-3.5" aria-hidden="true" />
                <span>Review scores</span>
              </Button>
              {exportDomainData ? (
                <div className="w-full [&>div]:w-full">
                  <SpecialistExportDownloadButton
                    domainData={exportDomainData}
                    agentId={effectiveDomainId as ExportAgentId}
                    variant="secondary"
                    className="w-full justify-center gap-1.5 text-xs font-semibold h-8.5"
                  />
                </div>
              ) : null}
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={onOpenReevaluate}
                className="w-full justify-center gap-1.5 text-xs font-semibold h-8.5"
              >
                <ArrowsClockwise className="size-3.5" aria-hidden="true" />
                <span>Re-evaluate</span>
              </Button>
            </div>

            {/* Specialist Summary Disclosure */}
            {(activeDomainData.summary || singleAgentMeta.requirement) && (
              <details className="group/summary border-t border-border pt-3">
                <summary className="flex min-h-6 cursor-pointer list-none items-center justify-between text-xs font-medium text-text-muted hover:text-text focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
                  <span>Specialist summary</span>
                  <CaretDown
                    className="size-3.5 shrink-0 transition-transform group-open/summary:rotate-180"
                    aria-hidden="true"
                  />
                </summary>
                <p className="mt-2 text-xs leading-relaxed text-text [overflow-wrap:anywhere]">
                  {activeDomainData.summary || singleAgentMeta.requirement}
                </p>
              </details>
            )}
          </div>

          {/* 2. Module Details Pane */}
          <div className="p-4 sm:p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-border pb-2.5">
              <h3 className="text-xs font-semibold text-text">
                Module details
              </h3>
              <span className="font-mono text-[11px] font-medium text-text-muted">
                {activeDomainData.version != null
                  ? `Revision ${activeDomainData.version}`
                  : (results?.legacy_notice || "Legacy form")}
              </span>
            </div>

            <dl className="space-y-2.5 text-xs">
              {results?.program ? (
                <div className="grid grid-cols-[5rem_minmax(0,1fr)] gap-2">
                  <dt className="text-text-muted">Program</dt>
                  <dd className="m-0 break-words font-medium text-text">{results.program}</dd>
                </div>
              ) : null}
              <div className="grid grid-cols-[5rem_minmax(0,1fr)] gap-2">
                <dt className="text-text-muted">Submitted</dt>
                <dd className="m-0 font-medium text-text tabular-nums">
                  {formatDateWithFallback(evaluation.submitted_at, "Not recorded")}
                </dd>
              </div>
              <div className="grid grid-cols-[5rem_minmax(0,1fr)] gap-2">
                <dt className="text-text-muted">Completed</dt>
                <dd className="m-0 font-medium text-text tabular-nums">
                  {formatDateWithFallback(evaluation.completed_at, "Not recorded")}
                </dd>
              </div>
              <div className="grid grid-cols-[5rem_minmax(0,1fr)] gap-2">
                <dt className="text-text-muted">Desk</dt>
                <dd className="m-0 font-medium text-text">{singleAgentMeta.shortLabel}</dd>
              </div>
              <div className="grid grid-cols-[5rem_minmax(0,1fr)] gap-2">
                <dt className="text-text-muted">Reference</dt>
                <dd className="m-0 font-medium text-text">{referenceBasis}</dd>
              </div>
            </dl>

            {/* Record details disclosure */}
            <details className="group/record border-t border-border pt-2.5">
              <summary className="flex min-h-6 cursor-pointer list-none items-center justify-between text-xs text-text-muted hover:text-text focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
                <span>Record details</span>
                <CaretDown
                  className="size-3.5 shrink-0 transition-transform group-open/record:rotate-180"
                  aria-hidden="true"
                />
              </summary>
              <dl className="mt-2 space-y-2 text-xs">
                <div>
                  <dt className="text-text-muted">Evaluation ID</dt>
                  <dd className="m-0 mt-0.5 break-all font-mono text-text">
                    {evaluation.evaluation_id}
                  </dd>
                </div>
                {activeDomainData.form_snapshot_id ? (
                  <div>
                    <dt className="text-text-muted">Form snapshot</dt>
                    <dd className="m-0 mt-0.5 break-all font-mono text-text">
                      {activeDomainData.form_snapshot_id}
                    </dd>
                  </div>
                ) : null}
              </dl>
            </details>
          </div>

          {/* 3. Human Review Governance Pane */}
          <div className="p-4 sm:p-5 space-y-3">
            <h3 className="text-xs font-semibold text-text">
              Human review
            </h3>
            <p className="text-xs leading-relaxed text-text-muted">
              Automated findings are advisory. CID reviewers keep the final decision for each criterion.
            </p>
            <div className="grid grid-cols-2 gap-2.5 pt-1">
              <div className="rounded-xs border border-border bg-surface p-2.5 text-center">
                <p className="text-2xl font-semibold text-text tabular-nums">{sortedCriteria.length}</p>
                <p className="mt-0.5 text-[11px] text-text-muted">Criteria</p>
              </div>
              <div className="rounded-xs border border-border bg-surface p-2.5 text-center">
                <p className="text-2xl font-semibold text-text tabular-nums">{reviewCount}</p>
                <p className="mt-0.5 text-[11px] text-text-muted">Overrides</p>
              </div>
            </div>
          </div>
        </aside>

        {/* RIGHT COLUMN: Criteria Breakdown (Integrated Grid Pane) */}
        <section
          aria-labelledby="evaluation-criteria-heading"
          className="min-w-0 bg-surface"
        >
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface px-4 py-3.5 sm:px-5">
            <div>
              <h3 id="evaluation-criteria-heading" className="text-sm font-semibold text-text">
                Criteria breakdown{" "}
                <span className="ml-1 font-normal tabular-nums text-text-muted">
                  ({displayCriteria.length})
                </span>
              </h3>
              <p className="mt-0.5 text-xs text-text-muted">
                {evidenceCount} with quoted evidence
              </p>
            </div>
            <span className="text-xs text-text-muted tabular-nums">
              Open a row to inspect evidence · Score / 4
            </span>
          </div>

          <div className="divide-y divide-border">
            {displayCriteria.map((criterion, index) => {
              const evidence = formatEvidenceText(criterion.evidence);
              const finding = cleanJustification(criterion.justification);
              const hasReview = Boolean(criterion.reviewer_correction);
              const scoreValue = Number(criterion.score ?? 0);
              const code = criterion.criterion_id;

              return (
                <details
                  key={`${effectiveDomainId}-${code || index}`}
                  className="group/criterion min-w-0 bg-surface"
                >
                  <summary className="grid min-h-12 cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-3 py-3 hover:bg-surface-subtle/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring sm:px-4 [&::-webkit-details-marker]:hidden">
                    <div className="flex min-w-0 items-start gap-2.5">
                      <CaretDown
                        className="mt-0.5 size-3.5 shrink-0 -rotate-90 text-text-muted transition-transform group-open/criterion:rotate-0"
                        aria-hidden="true"
                      />
                      <span className="min-w-14 shrink-0 font-mono text-xs text-text-muted">
                        {code}
                      </span>
                      <div className="min-w-0">
                        <h4 className="break-words text-sm font-medium leading-snug text-text">
                          {criterion.criterion_text}
                        </h4>
                        {criterion.description ? (
                          <p className="mt-0.5 text-xs leading-relaxed text-text-muted">
                            {criterion.description}
                          </p>
                        ) : null}
                        {(criterion.is_ungrounded || hasReview) && (
                          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs">
                            {criterion.is_ungrounded && (
                              <span className="inline-flex items-center gap-1 font-medium text-warning">
                                <WarningCircle className="size-3.5" aria-hidden="true" />
                                Ungrounded
                              </span>
                            )}
                            {hasReview && (
                              <span className="text-info font-medium">
                                Reviewer correction
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="sr-only">Score</span>
                      <span
                        className={cn(
                          "inline-flex items-center rounded-xs border px-2.5 py-1 font-mono text-xs font-semibold tabular-nums",
                          scoreValue >= 3
                            ? "border-success/30 bg-success-soft text-success"
                            : "border-warning/30 bg-warning-soft text-warning",
                        )}
                      >
                        {formatScore(scoreValue)} / 4
                      </span>
                    </div>
                  </summary>

                  <div className="grid border-t border-border bg-surface-subtle/20 xl:grid-cols-2">
                    <div className="border-b border-border px-4 py-4 sm:px-5 xl:border-b-0 xl:border-r">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-muted">
                        Quoted SLM evidence
                      </p>
                      {evidence ? (
                        <blockquote className="mt-2 border-l-2 border-primary/50 pl-3 text-sm leading-relaxed text-text whitespace-pre-line [overflow-wrap:anywhere]">
                          &ldquo;{evidence}&rdquo;
                        </blockquote>
                      ) : (
                        <p className="mt-2 text-sm text-text-muted">
                          No quoted evidence was returned.
                        </p>
                      )}
                      {criterion.is_ungrounded ? (
                        <p className="mt-3 text-xs font-medium text-warning">
                          Evidence requires reviewer confirmation.
                        </p>
                      ) : null}
                    </div>

                    <div className="px-4 py-4 sm:px-5">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text-muted">
                        Specialist finding
                      </p>
                      {finding ? (
                        <p className="mt-2 text-sm leading-relaxed text-text-muted">
                          {finding}
                        </p>
                      ) : (
                        <p className="mt-2 text-sm text-text-muted">
                          No specialist finding was returned.
                        </p>
                      )}

                      {hasReview ? (
                        <div className="mt-4 rounded-xs border border-info/30 bg-info-soft/25 p-3.5 space-y-1 text-xs">
                          <div className="flex items-center gap-2 font-semibold text-info">
                            <CheckCircle className="size-4 shrink-0" aria-hidden="true" />
                            <span>
                              {criterion.reviewer_correction?.action === "REJECT"
                                ? "Authoritative CID Human Override Flagged (Rejected)"
                                : "Authoritative CID Human Override Applied"}
                            </span>
                          </div>
                          {criterion.reviewer_correction?.score != null ? (
                            <p className="mt-1 font-mono text-xs font-semibold text-text">
                              Override Score: {criterion.reviewer_correction.score} / 4
                            </p>
                          ) : null}
                          {criterion.reviewer_correction?.justification ? (
                            <p className="mt-1 text-xs leading-relaxed text-text-muted">
                              <strong className="font-semibold text-text">
                                Reviewer Justification:{" "}
                              </strong>
                              {cleanJustification(criterion.reviewer_correction.justification)}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </details>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
