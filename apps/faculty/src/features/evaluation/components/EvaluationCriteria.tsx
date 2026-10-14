import { CaretDown, WarningCircle } from "@phosphor-icons/react";
import { cn } from "@equiped/ui";
import type { CriterionScoreItem } from "../types";
import {
  cleanJustification,
  formatEvidenceText,
  formatScore,
} from "../utils/scoreHelpers";
import {
  filterCriteria,
  type CriterionFilterType,
  type ScoreboardMetrics,
} from "../utils/scoreboardMetrics";

interface EvaluationCriteriaProps {
  criteria: CriterionScoreItem[];
  selectedFilter: CriterionFilterType;
  setSelectedFilter: (filter: CriterionFilterType) => void;
  metrics: ScoreboardMetrics;
}

export function EvaluationCriteria({
  criteria,
  selectedFilter,
  setSelectedFilter,
  metrics,
}: EvaluationCriteriaProps) {
  const { attentionCount, strongCount } = metrics;
  const correctedCount = criteria.filter((criterion) =>
    Boolean(criterion.reviewer_correction),
  ).length;
  const filteredCriteria = filterCriteria(criteria, selectedFilter);
  return (
    <section aria-labelledby="criteria-breakdown">
      <div className="flex flex-wrap items-center justify-between gap-3 py-3">
        <h3 id="criteria-breakdown" className="text-sm font-semibold text-text">
          Criteria breakdown
        </h3>
      </div>

      {criteria.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 pb-3">
          <button
            type="button"
            onClick={() => setSelectedFilter("ALL")}
            className={cn(
              "min-h-8 rounded-xs px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
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
              "inline-flex items-center gap-1 min-h-8 rounded-xs px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
              selectedFilter === "ATTENTION"
                ? "bg-warning text-warning-foreground font-semibold"
                : "bg-surface-subtle text-text-muted hover:bg-surface-subtle/80 hover:text-text",
            )}
          >
            {attentionCount > 0 && (
              <WarningCircle className="size-3 shrink-0" aria-hidden="true" />
            )}
            Needs attention ({attentionCount})
          </button>
          <button
            type="button"
            onClick={() =>
              setSelectedFilter(selectedFilter === "STRONG" ? "ALL" : "STRONG")
            }
            className={cn(
              "inline-flex items-center gap-1 min-h-8 rounded-xs px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
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
                "inline-flex items-center gap-1 min-h-8 rounded-xs px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-ring",
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
            const pageNumber = (
              criterion as unknown as { page_number?: number | string }
            ).page_number;
            const criterionText =
              criterion.criterion_text ||
              (criterion as unknown as { criterion?: string }).criterion ||
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
                      {criterion.description && (
                        <p className="mt-1 text-xs leading-relaxed text-text-muted">
                          {criterion.description}
                        </p>
                      )}
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
                    <span className="sr-only">Generated score</span>
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
                      <p className="text-xs font-semibold text-text-muted">
                        SLM evidence
                      </p>
                      {Boolean(pageNumber) && (
                        <span className="text-xs text-text-muted">
                          Page {pageNumber}
                        </span>
                      )}
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
                    {criterion.is_ungrounded && (
                      <p className="mt-3 text-xs font-medium text-warning">
                        Evidence requires reviewer confirmation.
                      </p>
                    )}
                  </div>

                  <div className="px-4 py-4 sm:px-5">
                    <p className="text-xs font-semibold text-text-muted">
                      Specialist finding
                    </p>
                    {criterion.justification ? (
                      <p className="mt-2 max-w-prose text-sm leading-relaxed text-text-muted">
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
                          {criterion.reviewer_correction.action === "REJECT"
                            ? "Finding rejected by reviewer"
                            : "Reviewer correction"}
                        </p>
                        {criterion.reviewer_correction.score != null ? (
                          <p className="mt-1 font-mono text-xs font-semibold text-text">
                            Override score:{" "}
                            {formatScore(criterion.reviewer_correction.score)} /
                            4
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
  );
}
