import { ChartBar } from "@phosphor-icons/react";
import { cn } from "@equiped/ui";
import type { TargetAgentMeta } from "@equiped/types";
import type { DomainScoreBlock } from "../types";
import {
  formatScore,
  monitoringPercentage,
  getAdjectivalRatingClasses,
} from "../utils/scoreHelpers";
import type {
  ScoreboardMetrics,
  CriterionFilterType,
} from "../utils/scoreboardMetrics";

interface EvaluationScoreSummaryProps {
  domainScore: DomainScoreBlock;
  meta: TargetAgentMeta;
  metrics: ScoreboardMetrics;
  selectedFilter: CriterionFilterType;
  setSelectedFilter: (filter: CriterionFilterType) => void;
  hasCorrections: boolean;
}
export function EvaluationScoreSummary({
  domainScore,
  meta,
  metrics,
  selectedFilter,
  setSelectedFilter,
  hasCorrections,
}: EvaluationScoreSummaryProps) {
  const score = domainScore.subtotal;
  const maxScore = domainScore.max_score || 4;
  const compliance = monitoringPercentage(score, maxScore);
  return (
    <section
      aria-labelledby="specialist-score-summary"
      className="border-b border-border pb-4"
    >
      <h3 id="specialist-score-summary" className="sr-only">
        {meta.fullName} performance score
      </h3>
      <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_11rem] md:items-center">
        <div className="min-w-0">
          <p className="text-xs font-medium text-text-muted">Generated score</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-semibold tabular-nums text-text">
                {formatScore(score)}
              </span>
              <span className="text-sm tabular-nums text-text-muted">
                / {formatScore(maxScore)}
              </span>
            </div>
            {domainScore.adjectival_rating && (
              <span
                className={cn(
                  "rounded-xs border px-2 py-1 text-xs font-medium",
                  getAdjectivalRatingClasses(domainScore.adjectival_rating),
                )}
              >
                {domainScore.adjectival_rating}
              </span>
            )}
            <span className="text-xs tabular-nums text-text-muted">
              {compliance}% of maximum score
            </span>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-text-muted">
            Automated assessment · Advisory
            {hasCorrections ? " · Corrections shown per criterion" : ""}
          </p>
        </div>
        <div
          className="border-t border-border pt-3 sm:border-l sm:border-t-0 sm:pl-4 sm:pt-0"
          aria-label="Score profile"
        >
          <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
            <div className="flex items-center gap-1.5">
              <ChartBar className="size-3.5 text-primary" aria-hidden="true" />
              Score profile
            </div>
          </div>
          <div
            className="mt-2 flex h-12 items-end gap-2"
            role="region"
            aria-label="Criteria score distribution from 4 to 1"
          >
            {metrics.scoreBuckets.map(({ bucket, count }) => {
              const height =
                count === 0
                  ? 8
                  : Math.max(22, (count / metrics.scoreBucketMax) * 100);
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
                      "text-xs tabular-nums transition-colors",
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
  );
}
