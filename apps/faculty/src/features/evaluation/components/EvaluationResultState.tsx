import { ArrowsClockwise, WarningCircle } from "@phosphor-icons/react";
import type { ITSOAssessment } from "@equiped/types";
import { historicalITSOResults } from "../utils/historicalITSOResults";
import { BUTTON_STYLES, Skeleton, cn } from "@equiped/ui";
import {
  EvaluationResultsView,
  type EvaluationResultsViewProps,
} from "./EvaluationResultsView";

export function EvaluationResultsLoading() {
  return (
    <section
      className="er-results"
      role="status"
      aria-label="Loading specialist results"
      aria-busy="true"
    >
      {/* Match the full-width result layout while the saved run loads. */}
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

      <div className="er-metadata">
        <Skeleton className="h-4 w-28" />
      </div>
      <div className="er-score-summary">
        <div className="er-score-layout er-score-layout-with-summary">
          <div className="er-score-main space-y-3">
            <Skeleton className="h-3 w-24" />
            <div className="flex items-center gap-3">
              <Skeleton className="h-8 w-28" />
              <Skeleton className="h-6 w-28" />
            </div>
            <Skeleton className="h-3 w-48 max-w-full" />
          </div>
          <div className="er-summary-copy space-y-2">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-3/4" />
          </div>
          <div className="er-score-profile space-y-2">
            <Skeleton className="h-3 w-24" />
            <div className="flex h-16 items-end gap-2">
              {[70, 95, 45, 25].map((height, index) => (
                <Skeleton
                  key={index}
                  className="flex-1"
                  style={{ height: `${height}%` }}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
      <div className="er-criteria-toolbar">
        <Skeleton className="h-4 w-36" />
        <div className="flex flex-wrap gap-2">
          {[16, 28, 20].map((width) => (
            <Skeleton
              key={width}
              className="h-8"
              style={{ width: `${width / 4}rem` }}
            />
          ))}
        </div>
      </div>
      <div className="er-criteria-list divide-y divide-border">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index} className="flex items-center gap-3 px-4 py-4">
            <Skeleton className="h-3 w-12 shrink-0" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton
                className={cn("h-4", index % 2 === 0 ? "w-3/4" : "w-1/2")}
              />
              <Skeleton className="h-3 w-2/3" />
            </div>
            <Skeleton className="h-7 w-16 shrink-0" />
          </div>
        ))}
      </div>
      <span className="sr-only">Loading the specialist results.</span>
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
        Retry loading results
      </button>
    </section>
  );
}

interface EvaluationResultStateProps extends Omit<
  EvaluationResultsViewProps,
  "results" | "domainScore"
> {
  assessment?: ITSOAssessment;
  isAssessmentPending?: boolean;
  results?: EvaluationResultsViewProps["results"] | null;
  domainScore?: EvaluationResultsViewProps["domainScore"] | null;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}
export function EvaluationResultState({
  results,
  assessment,
  isAssessmentPending,
  domainScore,
  isLoading,
  isError,
  onRetry,
  ...props
}: EvaluationResultStateProps) {
  if (isError && !results && !assessment)
    return <EvaluationResultsError onRetry={onRetry} />;
  if (assessment) {
    const archived = historicalITSOResults(assessment);
    return (
      <EvaluationResultsView
        {...props}
        results={archived}
        domainScore={archived.domain_scores.itso}
      />
    );
  }
  if (isAssessmentPending)
    return (
      <section
        role="status"
        className="border border-border bg-surface p-4 text-sm text-text"
      >
        <p>
          Assessment projection is not ready (202). No completed findings or
          score are inferred.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 font-semibold text-primary focus-visible:outline-2 focus-visible:outline-ring"
        >
          Refresh assessment
        </button>
      </section>
    );
  if (isLoading || !results) return <EvaluationResultsLoading />;
  if (!domainScore)
    return (
      <section
        className="border border-border px-6 py-10 text-sm text-text-muted"
        role="status"
      >
        No criteria recorded for this specialist evaluation.
      </section>
    );
  return (
    <EvaluationResultsView
      key={`${props.evaluation.evaluation_id}-${props.validAgent}`}
      {...props}
      results={results}
      domainScore={domainScore}
    />
  );
}
