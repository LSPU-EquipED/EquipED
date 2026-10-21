import { cn } from "@equiped/ui";
import { useId, useState } from "react";
import type { TargetAgentMeta } from "@equiped/types";
import type { DomainScoreBlock } from "../../types";
import {
  boundNarrative,
  cleanJustification,
  formatScore,
  getAdjectivalRatingClasses,
} from "../../utils/scoreHelpers";
import { summarizeITSODocumentEvidence } from "../../utils/criterionPresentation";
import type {
  ScoreboardMetrics,
  CriterionFilterType,
} from "../../utils/scoreboardMetrics";

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
  const [showFullSummary, setShowFullSummary] = useState(false);
  const summaryId = useId();
  const summary = cleanJustification(domainScore.summary);
  const preview = boundNarrative(summary, 440);
  const { unquotedCodes, hasNoConfidentialityConcern, hasUnverifiedRights } =
    summarizeITSODocumentEvidence(domainScore.criteria);
  const hasSummary = Boolean(
    summary ||
    unquotedCodes.length ||
    hasNoConfidentialityConcern ||
    hasUnverifiedRights,
  );
  return (
    <section
      aria-labelledby="specialist-score-summary"
      className="er-score-summary"
    >
      <h3 id="specialist-score-summary" className="sr-only">
        {meta.fullName} performance score
      </h3>
      <div
        className={cn(
          "er-score-layout",
          hasSummary && "er-score-layout-with-summary",
        )}
      >
        <div className="er-score-main">
          <p className="er-label">Generated score</p>
          <div className="er-score-line">
            <div className="flex items-baseline gap-1.5">
              <span className="er-score-value">{formatScore(score)}</span>
              <span className="er-score-scale">/ {formatScore(maxScore)}</span>
            </div>
            {domainScore.adjectival_rating && (
              <span
                className={cn(
                  "er-rating",
                  getAdjectivalRatingClasses(domainScore.adjectival_rating),
                )}
              >
                {domainScore.adjectival_rating}
              </span>
            )}
          </div>
          <p className="er-score-note">
            Automated assessment · Advisory
            {hasCorrections ? " · Corrections shown per criterion" : ""}
          </p>
        </div>
        {hasSummary && (
          <div className="er-summary-copy">
            <p className="er-label">Specialist summary</p>
            {summary && (
              <p id={summaryId}>{showFullSummary ? summary : preview}</p>
            )}
            {preview !== summary && (
              <button
                type="button"
                aria-expanded={showFullSummary}
                aria-controls={summaryId}
                onClick={() => setShowFullSummary(!showFullSummary)}
                className="mt-2 text-xs font-semibold text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
              >
                {showFullSummary ? "Show less" : "Show full summary"}
              </button>
            )}
            {unquotedCodes.length > 0 && (
              <p className="mt-2 text-sm text-text-muted">
                No SLM quotations recorded: {unquotedCodes.join(", ")}. See each
                finding for review limits.
              </p>
            )}
            {(hasNoConfidentialityConcern || hasUnverifiedRights) && (
              <p className="mt-2 text-sm text-text-muted">
                {hasNoConfidentialityConcern &&
                  "Confidentiality: no concern detected in reviewed text."}
                {hasNoConfidentialityConcern && hasUnverifiedRights && " "}
                {hasUnverifiedRights && "Rights and permissions: unverified."}
              </p>
            )}
          </div>
        )}
        <div className="er-score-profile" aria-label="Score profile">
          <div className="er-profile-heading">
            <span>Score profile</span>
            <span>Filter by score</span>
          </div>
          <div
            className="er-score-buckets"
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
                  className={cn("er-score-bucket", isSelected && "is-selected")}
                >
                  <span className="er-bucket-count" aria-hidden="true">
                    {count}
                  </span>
                  <div
                    className={cn(
                      "er-bucket-track",
                      isSelected ? "bg-primary-soft" : "bg-surface-subtle",
                    )}
                    aria-hidden="true"
                  >
                    <span
                      className={cn(
                        "er-bucket-bar",
                        barColor,
                        isSelected && "brightness-110",
                      )}
                      style={{ height: `${height}%` }}
                    />
                  </div>
                  <span
                    className={cn(
                      "er-bucket-label",
                      isSelected ? "font-bold text-text" : "text-text-muted",
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
