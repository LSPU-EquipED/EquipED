import { ArrowsClockwise, WarningCircle } from "@phosphor-icons/react";
import { BUTTON_STYLES, Skeleton, cn } from "@equiped/ui";
import {
  EvaluationResultsView,
  type EvaluationResultsViewProps,
} from "./EvaluationResultsView";

export function EvaluationResultsLoading() {
  return (
    <section
      className="min-w-0"
      role="status"
      aria-label="Loading specialist results"
      aria-busy="true"
    >
      {/* Header Skeleton matching EvaluationResultsView */}
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

      {/* Two-column layout matching EvaluationResultsView */}
      <div className="grid min-w-0 gap-4 pt-4 xl:grid-cols-[14rem_minmax(0,1fr)] xl:gap-6">
        {/* Left Column: Module Details Dossier */}
        <aside
          className="hidden min-w-0 border-r border-border pr-5 xl:block space-y-4"
          aria-label="Evaluation metadata loading"
        >
          <Skeleton className="h-3.5 w-24" />
          <div className="space-y-4 py-3">
            <div className="flex items-center justify-between gap-2 border-b border-border pb-3">
              <Skeleton className="h-5 w-20 rounded-xs" />
              <Skeleton className="h-3.5 w-24" />
            </div>
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <div
                  key={index}
                  className="grid grid-cols-[5.25rem_minmax(0,1fr)] gap-2"
                >
                  <Skeleton className="h-3 w-14" />
                  <Skeleton className="h-3 w-28" />
                </div>
              ))}
            </div>
            <div className="mt-4 border-t border-border pt-3">
              <Skeleton className="h-3.5 w-24" />
            </div>
          </div>
        </aside>

        {/* Right Column: Scorecard & Criteria Ledger */}
        <section
          className="min-w-0 space-y-4"
          aria-label="Specialist scorecard loading"
        >
          {/* Score Summary Banner */}
          <div className="border-b border-border pb-3">
            <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_13rem] md:items-center">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <Skeleton className="h-8 w-24" />
                <Skeleton className="h-6 w-28 rounded-xs" />
                <Skeleton className="h-3.5 w-28" />
                <Skeleton className="h-3.5 w-36" />
              </div>
              <div className="border-t border-border pt-3 md:border-l md:border-t-0 md:pl-4 md:pt-0">
                <Skeleton className="h-3.5 w-20 mb-2" />
                <div className="flex h-12 items-end gap-2">
                  {[70, 95, 45, 25].map((h, i) => (
                    <div
                      key={i}
                      className="flex min-w-0 flex-1 flex-col items-center gap-1"
                    >
                      <div className="flex h-9 w-full items-end rounded-xs bg-surface-subtle px-1">
                        <Skeleton
                          className="w-full rounded-xs"
                          style={{ height: `${h}%` }}
                        />
                      </div>
                      <Skeleton className="h-2 w-2" />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Specialist Summary Accordion Skeleton */}
          <div className="border-b border-border py-2 flex items-center gap-2">
            <Skeleton className="size-3.5 rounded-xs" />
            <Skeleton className="h-3.5 w-32" />
          </div>

          {/* Criteria Breakdown Header & Triage Filter Tabs */}
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3 py-1">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-56" />
            </div>
            <div className="flex flex-wrap items-center gap-1.5 pb-2">
              <Skeleton className="h-6 w-16 rounded-xs" />
              <Skeleton className="h-6 w-28 rounded-xs" />
              <Skeleton className="h-6 w-20 rounded-xs" />
            </div>

            {/* Criteria Rows */}
            <div className="divide-y divide-border border-y border-border">
              {Array.from({ length: 4 }).map((_, index) => (
                <div
                  key={index}
                  className="grid min-h-12 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-3 py-3 sm:px-4"
                >
                  <div className="flex min-w-0 items-center gap-2.5">
                    <Skeleton className="size-3.5 shrink-0 rounded-xs" />
                    <Skeleton className="h-3 w-12 shrink-0 font-mono" />
                    <div className="min-w-0 flex-1 space-y-1">
                      <Skeleton
                        className={cn(
                          "h-4",
                          index % 2 === 0 ? "w-3/4" : "w-1/2",
                        )}
                      />
                    </div>
                  </div>
                  <Skeleton className="h-6 w-16 shrink-0 rounded-xs" />
                </div>
              ))}
            </div>
          </div>
        </section>
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
  results?: EvaluationResultsViewProps["results"] | null;
  domainScore?: EvaluationResultsViewProps["domainScore"] | null;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}
export function EvaluationResultState({
  results,
  domainScore,
  isLoading,
  isError,
  onRetry,
  ...props
}: EvaluationResultStateProps) {
  if (isError && !results) return <EvaluationResultsError onRetry={onRetry} />;
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
