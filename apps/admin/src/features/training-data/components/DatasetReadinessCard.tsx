import { Badge, Button, Skeleton, TYPOGRAPHY } from '@equiped/ui';
import type { StatusVariant } from '@equiped/ui';
import { useDatasetPreparation } from '../hooks/useDatasetPreparation';
import type { ReadinessTier } from '../types';
import { DatasetNotes } from './DatasetNotes';

// Volume alone does not validate an adapter; the highest tier is informational.
const TIER_BADGE: Record<ReadinessTier, { label: string; variant: StatusVariant }> = {
  empty: { label: 'No pairs', variant: 'neutral' },
  'single-evaluation': { label: 'Single evaluation', variant: 'warning' },
  small: { label: 'Limited data', variant: 'warning' },
  reasonable: { label: 'Enough to try', variant: 'info' },
};

interface DatasetReadinessCardProps {
  agentId: string;
  onPrepare: () => void;
  isPreparing: boolean;
  hasHandoff: boolean;
  preparationError: string | null;
}

export function DatasetReadinessCard({
  agentId,
  onPrepare,
  isPreparing,
  hasHandoff,
  preparationError,
}: DatasetReadinessCardProps) {
  const { data, isLoading, isError, refetch, readiness, comparison, reviewerNote } =
    useDatasetPreparation(agentId);

  return (
    <section
      aria-labelledby="dataset-preparation-title"
      className="overflow-hidden rounded-md border border-border bg-surface"
    >
      <div className="grid lg:grid-cols-[minmax(0,1.15fr)_minmax(18rem,1fr)]">
        <div className="min-w-0 space-y-4 p-4 sm:p-5">
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 id="dataset-preparation-title" className={TYPOGRAPHY.headingSm}>
              Dataset preparation
            </h2>
            {readiness && !isError && !isLoading && (
              <Badge className="tracking-normal" variant={TIER_BADGE[readiness.tier].variant}>
                {TIER_BADGE[readiness.tier].label}
              </Badge>
            )}
          </div>
          {isLoading ? (
            <div
              role="status"
              aria-busy="true"
              className="divide-y divide-border border-y border-border"
            >
              <span className="sr-only">Checking dataset…</span>
              {[0, 1, 2].map((index) => (
                <div key={index} className="flex items-center justify-between py-2.5">
                  <Skeleton className="h-5 w-20" />
                  <Skeleton className="h-5 w-8" />
                </div>
              ))}
            </div>
          ) : isError || !data || !readiness ? (
            <div
              role="alert"
              className="flex flex-wrap items-center gap-3 text-sm text-destructive"
            >
              <p>Failed to check dataset readiness. Try again to prepare a run.</p>
              <Button variant="secondary" size="sm" onClick={() => void refetch()}>
                Retry readiness
              </Button>
            </div>
          ) : (
            <dl className="divide-y divide-border border-y border-border">
              {[
                ['Pairs', data.pair_count],
                ['Evaluations', data.evaluation_count],
                ['Reviewers', data.reviewer_count],
              ].map(([label, value]) => (
                <div key={label} className="flex items-baseline justify-between gap-4 py-2.5">
                  <dt className="text-[13px] leading-5 text-text-muted">{label}</dt>
                  <dd className="text-base font-semibold leading-5 tabular-nums text-text">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <Button
              onClick={onPrepare}
              disabled={
                isPreparing || isLoading || isError || !data || data.pair_count <= 0 || hasHandoff
              }
              aria-describedby={hasHandoff ? 'training-handoff-reminder' : undefined}
              aria-busy={isPreparing}
              className="w-full sm:w-auto"
            >
              {isPreparing ? 'Preparing run…' : 'Prepare training run'}
            </Button>
            <p className="text-xs leading-4 text-text-muted">
              Training continues in your notebook.
            </p>
          </div>
        </div>
        <DatasetNotes
          data={data}
          readiness={readiness}
          comparison={comparison}
          reviewerNote={reviewerNote}
          isLoading={isLoading}
          isError={isError}
        />
      </div>
      {hasHandoff && (
        <p
          id="training-handoff-reminder"
          className="border-t border-border px-4 py-3 text-sm text-text-muted sm:px-5"
        >
          Save the notebook URLs below before preparing another run.
        </p>
      )}
      {preparationError && (
        <p
          role="alert"
          className="border-t border-border bg-destructive-soft px-4 py-3 text-sm text-destructive sm:px-5"
        >
          {preparationError}
        </p>
      )}
    </section>
  );
}
