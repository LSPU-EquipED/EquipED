import { useState, useMemo } from "react";
import { Link } from "@tanstack/react-router";
import {
  ArrowLeft,
  ArrowSquareOut,
  ArrowsClockwise,
  CaretDown,
  ChartBar,
  FolderOpen,
  NotePencil,
  WarningCircle,
} from "@phosphor-icons/react";
import { Button } from "@equiped/ui";
import { cn } from "@equiped/ui";
import type {
  TargetAgentMeta,
  TargetAgent,
  ClientDocument,
} from "@equiped/types";
import type {
  DeskQueueItem,
  DomainScoreBlock,
  EvaluationResultsResponse,
} from "../types";
import { SpecialistExportDownloadButton } from "./ExportDocument";
import {
  cleanJustification,
  formatEvidenceText,
  formatScore,
  monitoringPercentage,
  getAdjectivalRatingClasses,
} from "../utils/scoreHelpers";

import { formatDateWithFallback } from "../utils/dateFormatting";
import {
  calculateScoreboardMetrics,
  filterCriteria,
  type CriterionFilterType,
} from "../utils/scoreboardMetrics";

export interface SpecialistResultsScoreboardProps {
  results: EvaluationResultsResponse;
  domainScore?: DomainScoreBlock | null;
  meta: TargetAgentMeta;
  validAgent: TargetAgent;
  activeItem: DeskQueueItem | null;
  activeDocument: ClientDocument | null;
  latestJobId?: string | null;
  onOpenReviewModal: () => void;
  onOpenReevaluateModal: () => void;
}

type CriterionFilter = CriterionFilterType;

export function SpecialistResultsScoreboard({
  results,
  domainScore,
  meta,
  validAgent,
  activeItem,
  activeDocument,
  latestJobId,
  onOpenReviewModal,
  onOpenReevaluateModal,
}: SpecialistResultsScoreboardProps) {
  const [selectedFilter, setSelectedFilter] = useState<CriterionFilter>("ALL");
  const criteria = useMemo(() => domainScore?.criteria ?? [], [domainScore?.criteria]);
  const displayTitle =
    activeDocument?.lessonTitle ||
    activeDocument?.courseTitle ||
    activeItem?.title ||
    activeDocument?.title ||
    "Course Module";
  const courseCode =
    activeItem?.course_code ||
    activeDocument?.courseCode ||
    "Course not specified";
  const program =
    activeItem?.program ||
    activeDocument?.program ||
    results.program ||
    "Program not specified";
  const uploadDate = formatDateWithFallback(
    activeItem?.uploaded_at || activeDocument?.uploadedAt,
    "Not specified",
  );
  const completedDate = formatDateWithFallback(
    results.completed_at,
    "Not specified",
  );
  const evaluationId = latestJobId || results.evaluation_id;
  const score = domainScore?.subtotal ?? 0;
  const maxScore = domainScore?.max_score || 4;
  const compliance = monitoringPercentage(score, maxScore);
  const { attentionCount, strongCount, scoreBuckets, scoreBucketMax } = useMemo(
    () => calculateScoreboardMetrics(criteria),
    [criteria],
  );
  const correctedCount = criteria.filter(
    (criterion) => Boolean(criterion.reviewer_correction),
  ).length;
  const referenceBasis = meta.requiresCurriculum
    ? "Institutional curriculum"
    : "Specialist rubric";

  const filteredCriteria = useMemo(() => {
    return filterCriteria(criteria, selectedFilter);
  }, [criteria, selectedFilter]);

  const metadata = (
    <div className="space-y-4 py-3">
      <div className="flex items-center justify-between gap-2 border-b border-border pb-3">
        <span className="inline-flex items-center gap-1.5 rounded-xs border border-primary/30 bg-primary-soft px-2 py-0.5 text-xs font-semibold text-primary">
          SLM Module
        </span>
        <Link
          to="/documents"
          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
        >
          <FolderOpen className="size-3.5" aria-hidden="true" />
          <span>SLM Storage</span>
          <ArrowSquareOut className="size-3" aria-hidden="true" />
        </Link>
      </div>

      <dl className="space-y-3 text-xs">
        {[
          ["Course", courseCode],
          ["Program", program],
          ["Uploaded", uploadDate],
          ["Completed", completedDate],
          ["Desk", meta.shortLabel],
          ["Reference", referenceBasis],
        ].map(([label, value]) => (
          <div
            key={label}
            className="grid grid-cols-[5.25rem_minmax(0,1fr)] gap-2"
          >
            <dt className="text-text-muted">{label}</dt>
            <dd className="m-0 break-words font-medium text-text">{value}</dd>
          </div>
        ))}
      </dl>
      <details className="group/record mt-4 border-t border-border pt-3">
        <summary className="flex min-h-8 cursor-pointer list-none items-center justify-between gap-2 text-xs font-medium text-text-muted hover:text-text focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
          Record details
          <CaretDown
            className="size-3.5 shrink-0 group-open/record:rotate-180"
            aria-hidden="true"
          />
        </summary>
        <dl className="mt-2 space-y-3 text-xs">
          <div>
            <dt className="text-text-muted">Evaluation ID</dt>
            <dd className="m-0 mt-1 break-all font-mono text-text">
              {evaluationId}
            </dd>
          </div>
          {domainScore?.version != null && (
            <div>
              <dt className="text-text-muted">Rubric version</dt>
              <dd className="m-0 mt-1 text-text">{domainScore.version}</dd>
            </div>
          )}
          {domainScore?.form_snapshot_id && (
            <div>
              <dt className="text-text-muted">Form snapshot</dt>
              <dd className="m-0 mt-1 break-all font-mono text-text">
                {domainScore.form_snapshot_id}
              </dd>
            </div>
          )}
        </dl>
      </details>
    </div>
  );

  return (
    <div className="min-w-0">
      <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-border pb-3">
        <div className="min-w-0 flex-1 basis-72">
          <Link
            to="/specialists/$agentId"
            params={{ agentId: validAgent }}
            className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-semibold text-text-muted transition-colors hover:text-text focus-visible:outline-2 focus-visible:outline-ring"
          >
            <ArrowLeft className="size-3.5 shrink-0" aria-hidden="true" />
            <span>Back to {meta.shortLabel} Desk</span>
          </Link>
          <h2 className="break-words text-lg font-semibold leading-snug text-text [overflow-wrap:anywhere]">
            {displayTitle}
          </h2>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-muted">
            <span>{meta.shortLabel} desk</span>
            <span aria-hidden="true">·</span>
            <span>{courseCode}</span>
            <span aria-hidden="true">·</span>
            <span>{program}</span>
          </p>
        </div>
        <div className="flex max-w-full flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={!domainScore}
            onClick={onOpenReviewModal}
            className="gap-1.5 text-xs font-semibold"
          >
            <NotePencil className="size-3.5" aria-hidden="true" />
            Review scores
          </Button>
          {domainScore ? (
            <SpecialistExportDownloadButton
              domainData={{
                agentId: validAgent,
                documentTitle:
                  results.document_title ||
                  activeItem?.title ||
                  activeDocument?.title ||
                  "Course Module",
                program:
                  results.program ||
                  activeItem?.program ||
                  activeDocument?.program ||
                  null,
                courseCode:
                  activeItem?.course_code || activeDocument?.courseCode || null,
                evaluationId,
                criteria,
                subtotal: domainScore.subtotal,
                max_score: maxScore,
                status:
                  domainScore.status ||
                  results.evaluation_status ||
                  "COMPLETED",
                adjectival_rating: domainScore.adjectival_rating ?? undefined,
                summary: domainScore.summary,
                version: domainScore.version,
                form_snapshot_id: domainScore.form_snapshot_id ?? undefined,
                results,
                document: activeDocument ?? null,
              }}
              agentId={validAgent}
              variant="secondary"
            />
          ) : null}

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onOpenReevaluateModal}
            aria-label="Re-evaluate"
            title="Re-evaluate"
            className="size-9 shrink-0 p-0"
          >
            <ArrowsClockwise className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </header>

      <div className="grid min-w-0 gap-4 pt-4 xl:grid-cols-[18rem_minmax(0,1fr)] xl:gap-7">
        <aside
          className="hidden min-w-0 border-r border-border pr-5 xl:block"
          aria-label="Evaluation metadata"
        >
          <h3 className="text-xs font-semibold text-text">Module details</h3>
          {metadata}
        </aside>
        <details className="group/metadata border-b border-border pb-3 xl:hidden">
          <summary className="flex min-h-8 cursor-pointer list-none items-center justify-between text-xs font-semibold text-text focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
            Module details
            <CaretDown
              className="size-4 group-open/metadata:rotate-180"
              aria-hidden="true"
            />
          </summary>
          {metadata}
        </details>

        <section className="min-w-0" aria-label="Specialist scorecard">
          <section
            aria-labelledby="specialist-score-summary"
            className="border-b border-border pb-3"
          >
            <h3 id="specialist-score-summary" className="sr-only">
              {meta.fullName} performance score
            </h3>
            <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_13rem] md:items-center">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <div className="flex items-baseline gap-1.5">
                  <span className="text-2xl font-semibold tabular-nums text-text">
                    {domainScore ? formatScore(score) : "Unavailable"}
                  </span>
                  {domainScore && (
                    <span className="text-xs tabular-nums text-text-muted">
                      / {formatScore(maxScore)}
                    </span>
                  )}
                </div>
                {domainScore?.adjectival_rating && (
                  <span
                    className={cn(
                      "rounded-xs border px-2 py-1 text-xs font-medium",
                      getAdjectivalRatingClasses(domainScore.adjectival_rating),
                    )}
                  >
                    {domainScore.adjectival_rating}
                  </span>
                )}
                {domainScore && (
                  <span className="text-xs tabular-nums text-text-muted">
                    {compliance}% compliance
                  </span>
                )}
                {criteria.length > 0 && (
                  <span className="text-xs tabular-nums text-text-muted">
                    {criteria.length} criteria · {strongCount} strong
                  </span>
                )}
                {attentionCount > 0 && (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-warning">
                    <WarningCircle className="size-3.5" aria-hidden="true" />
                    {attentionCount} need attention
                  </span>
                )}
                <span className="text-xs text-text-muted sm:ml-auto">
                  Automated assessment · Advisory
                </span>
              </div>
              <div
                className="border-t border-border pt-3 md:border-l md:border-t-0 md:pl-4 md:pt-0"
                aria-label="Score profile"
              >
                <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
                  <div className="flex items-center gap-1.5">
                    <ChartBar
                      className="size-3.5 text-primary"
                      aria-hidden="true"
                    />
                    Score profile
                  </div>
                  {typeof selectedFilter === "number" && (
                    <button
                      type="button"
                      onClick={() => setSelectedFilter("ALL")}
                      className="text-[10px] text-text-muted underline hover:text-text focus-visible:outline-2 focus-visible:outline-ring"
                    >
                      Reset
                    </button>
                  )}
                </div>
                <div
                  className="mt-2 flex h-12 items-end gap-2"
                  role="region"
                  aria-label="Criteria score distribution from 4 to 1"
                >
                  {scoreBuckets.map(({ bucket, count }) => {
                    const height =
                      count === 0
                        ? 8
                        : Math.max(22, (count / scoreBucketMax) * 100);
                    const isSelected = selectedFilter === bucket;
                    const barColor =
                      bucket >= 4
                        ? "bg-success"
                        : bucket === 3
                          ? "bg-primary"
                          : bucket === 2
                            ? "bg-warning"
                            : "bg-destructive";
                    return (
                      <button
                        key={bucket}
                        type="button"
                        onClick={() =>
                          setSelectedFilter(
                            isSelected ? "ALL" : (bucket as 4 | 3 | 2 | 1),
                          )
                        }
                        disabled={count === 0}
                        aria-pressed={isSelected}
                        title={`Filter score ${bucket} (${count} criteria)`}
                        aria-label={`Score ${bucket}: ${count} criteria`}
                        className={cn(
                          "group flex min-w-0 flex-1 flex-col items-center gap-1 rounded-xs transition-colors focus-visible:outline-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-40",
                          isSelected && "ring-2 ring-primary ring-offset-1",
                        )}
                      >
                        <div
                          className={cn(
                            "flex h-9 w-full items-end rounded-xs px-1 transition-colors",
                            isSelected
                              ? "bg-primary-soft"
                              : "bg-surface-subtle group-hover:bg-surface-subtle/80",
                          )}
                          aria-hidden="true"
                        >
                          <span
                            className={cn(
                              "block w-full rounded-xs transition-all",
                              barColor,
                              isSelected && "brightness-110",
                            )}
                            style={{ height: `${height}%` }}
                          />
                        </div>
                        <span
                          className={cn(
                            "text-[10px] tabular-nums transition-colors",
                            isSelected
                              ? "font-bold text-text"
                              : "text-text-muted group-hover:text-text",
                          )}
                        >
                          {bucket}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </section>

          {domainScore?.summary && (
            <details className="group/summary border-b border-border py-2">
              <summary className="flex min-h-8 cursor-pointer list-none items-center gap-2 text-xs font-medium text-text-muted focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
                <CaretDown
                  className="size-3.5 -rotate-90 group-open/summary:rotate-0"
                  aria-hidden="true"
                />
                Specialist summary
              </summary>
              <p className="pb-2 pt-1 text-sm leading-relaxed text-text [overflow-wrap:anywhere]">
                {domainScore.summary}
              </p>
            </details>
          )}

          <section aria-labelledby="criteria-breakdown">
            <div className="flex flex-wrap items-center justify-between gap-3 py-3">
              <h3
                id="criteria-breakdown"
                className="text-sm font-semibold text-text"
              >
                Criteria breakdown{" "}
                <span className="ml-1 font-normal tabular-nums text-text-muted">
                  ({criteria.length})
                </span>
              </h3>
              <span className="pr-3 text-xs text-text-muted">
                Open a row to inspect evidence · Score / 4
              </span>
            </div>

            {criteria.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pb-3">
                <button
                  type="button"
                  onClick={() => setSelectedFilter("ALL")}
                  className={cn(
                    "rounded-xs px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
                    selectedFilter === "ALL"
                      ? "bg-primary text-primary-foreground font-semibold"
                      : "bg-surface-subtle text-text-muted hover:bg-surface-subtle/80 hover:text-text",
                  )}
                >
                  All ({criteria.length})
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setSelectedFilter(
                      selectedFilter === "ATTENTION" ? "ALL" : "ATTENTION",
                    )
                  }
                  className={cn(
                    "inline-flex items-center gap-1 rounded-xs px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
                    selectedFilter === "ATTENTION"
                      ? "bg-warning text-warning-foreground font-semibold"
                      : "bg-surface-subtle text-text-muted hover:bg-surface-subtle/80 hover:text-text",
                  )}
                >
                  {attentionCount > 0 && (
                    <WarningCircle
                      className="size-3 shrink-0"
                      aria-hidden="true"
                    />
                  )}
                  Needs attention ({attentionCount})
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setSelectedFilter(
                      selectedFilter === "STRONG" ? "ALL" : "STRONG",
                    )
                  }
                  className={cn(
                    "inline-flex items-center gap-1 rounded-xs px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
                    selectedFilter === "STRONG"
                      ? "bg-success text-success-foreground font-semibold"
                      : "bg-surface-subtle text-text-muted hover:bg-surface-subtle/80 hover:text-text",
                  )}
                >
                  Strong ({strongCount})
                </button>
                {correctedCount > 0 && (
                  <button
                    type="button"
                    onClick={() =>
                      setSelectedFilter(
                        selectedFilter === "CORRECTED" ? "ALL" : "CORRECTED",
                      )
                    }
                    className={cn(
                      "inline-flex items-center gap-1 rounded-xs px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
                      selectedFilter === "CORRECTED"
                        ? "bg-info text-info-foreground font-semibold"
                        : "bg-surface-subtle text-text-muted hover:bg-surface-subtle/80 hover:text-text",
                    )}
                  >
                    Corrected ({correctedCount})
                  </button>
                )}
                {typeof selectedFilter === "number" && (
                  <span className="inline-flex items-center gap-1.5 rounded-xs border border-primary/30 bg-primary-soft px-2 py-0.5 text-xs font-medium text-primary">
                    Score: {selectedFilter} ({filteredCriteria.length})
                    <button
                      type="button"
                      onClick={() => setSelectedFilter("ALL")}
                      aria-label="Clear score filter"
                      className="ml-0.5 hover:text-text"
                    >
                      ×
                    </button>
                  </span>
                )}
              </div>
            )}

            {criteria.length === 0 ? (
              <div className="border border-dashed border-border px-5 py-10 text-center text-sm text-text-muted">
                No criteria were returned for this specialist evaluation.
              </div>
            ) : filteredCriteria.length === 0 ? (
              <div className="border border-dashed border-border px-5 py-8 text-center text-xs text-text-muted">
                <p>No criteria match the selected filter.</p>
                <button
                  type="button"
                  onClick={() => setSelectedFilter("ALL")}
                  className="mt-2 text-xs font-semibold text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
                >
                  Reset filter to view all {criteria.length} criteria
                </button>
              </div>
            ) : (
              <div className="divide-y divide-border border-y border-border">
                {filteredCriteria.map((criterion) => {
                  const code =
                    (criterion as unknown as { code?: string }).code ||
                    criterion.criterion_id;
                  const criterionText =
                    criterion.criterion_text ||
                    (criterion as unknown as { criterion?: string })
                      .criterion ||
                    criterion.description;

                  return (
                    <details
                      key={code}
                      className="group/criterion min-w-0 bg-surface"
                    >
                      <summary className="grid min-h-12 cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-3 py-3 hover:bg-surface-subtle/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring sm:px-4 [&::-webkit-details-marker]:hidden">
                        <div className="flex min-w-0 items-start gap-2.5">
                          <CaretDown
                            className="mt-0.5 size-3.5 shrink-0 -rotate-90 text-text-muted group-open/criterion:rotate-0"
                            aria-hidden="true"
                          />
                          <span className="min-w-12 shrink-0 font-mono text-xs text-text-muted">
                            {code}
                          </span>
                          <div className="min-w-0">
                            <h4 className="break-words text-sm font-medium leading-snug text-text">
                              {criterionText}
                            </h4>
                            {(criterion.is_ungrounded ||
                              criterion.reviewer_correction) && (
                              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs">
                                {criterion.is_ungrounded && (
                                  <span className="inline-flex items-center gap-1 text-warning">
                                    <WarningCircle
                                      className="size-3.5"
                                      aria-hidden="true"
                                    />
                                    Check evidence
                                  </span>
                                )}
                                {criterion.reviewer_correction && (
                                  <span className="text-info">
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
                              "inline-flex items-center rounded-xs border px-2.5 py-1 font-mono text-xs font-semibold",
                              (criterion.score ?? 0) >= 3
                                ? "border-success/30 bg-success-soft text-success"
                                : "border-warning/30 bg-warning-soft text-warning",
                            )}
                          >
                            {formatScore(criterion.score)} / 4
                          </span>
                        </div>
                      </summary>

                      <div className="grid border-t border-border xl:grid-cols-2">
                        <div className="border-b border-border px-4 py-4 sm:px-5 xl:border-b-0 xl:border-r">
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-[11px] font-semibold text-text-muted">
                              SLM evidence
                            </p>
                            <span className="text-[11px] font-medium text-text-muted">
                              SLM Document
                              {(criterion as unknown as { page_number?: number | string }).page_number
                                ? ` · Page ${(criterion as unknown as { page_number?: number | string }).page_number}`
                                : ""}
                            </span>
                          </div>
                          {criterion.evidence ? (
                            <blockquote className="mt-2 border-l-2 border-primary/50 pl-3 text-sm leading-relaxed text-text whitespace-pre-line [overflow-wrap:anywhere]">
                              &ldquo;{formatEvidenceText(criterion.evidence)}
                              &rdquo;
                            </blockquote>
                          ) : (
                            <p className="mt-2 text-sm text-text-muted">
                              No quoted evidence was returned.
                            </p>
                          )}
                          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border/50 pt-2">
                            <Link
                              to="/documents"
                              className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
                            >
                              <FolderOpen className="size-3 shrink-0" aria-hidden="true" />
                              <span>View in SLM Storage</span>
                              <ArrowSquareOut className="size-2.5 shrink-0" aria-hidden="true" />
                            </Link>
                            {criterion.is_ungrounded ? (
                              <span className="inline-flex items-center gap-1 text-xs font-medium text-warning">
                                <WarningCircle className="size-3.5 shrink-0" aria-hidden="true" />
                                Evidence requires reviewer confirmation
                              </span>
                            ) : null}
                          </div>
                        </div>

                        <div className="px-4 py-4 sm:px-5">
                          <p className="text-[11px] font-semibold text-text-muted">
                            Specialist finding
                          </p>
                          {criterion.justification ? (
                            <p className="mt-2 text-sm leading-relaxed text-text-muted">
                              {cleanJustification(criterion.justification)}
                            </p>
                          ) : (
                            <p className="mt-2 text-sm text-text-muted">
                              No specialist finding was returned.
                            </p>
                          )}

                          {criterion.reviewer_correction ? (
                            <div className="mt-4 border-l-2 border-info bg-info-soft/25 px-3 py-2.5">
                              <p className="text-[11px] font-semibold text-info">
                                CID reviewer override
                              </p>
                              {criterion.reviewer_correction.score != null ? (
                                <p className="mt-1 font-mono text-xs font-semibold text-text">
                                  Override score:{" "}
                                  {formatScore(
                                    criterion.reviewer_correction.score,
                                  )}{" "}
                                  / 4
                                </p>
                              ) : null}
                              {criterion.reviewer_correction.justification ? (
                                <p className="mt-1 text-xs leading-relaxed text-text-muted">
                                  {cleanJustification(
                                    criterion.reviewer_correction.justification,
                                  )}
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
            )}
          </section>
        </section>
      </div>
    </div>
  );
}
