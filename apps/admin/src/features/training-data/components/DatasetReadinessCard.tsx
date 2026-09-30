import { Badge, Button, Skeleton, TYPOGRAPHY } from '@equiped/ui';
import type { StatusVariant } from '@equiped/ui';
import { useDatasetPreparation } from '../hooks/useDatasetPreparation';
import type { ReadinessTier } from '../utils/trainingData.utils';
import { describeFunnel, RULE_OF_THUMB_NOTE, SEEDED_DATA_NOTE } from '../utils/trainingData.utils';

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
    <section aria-labelledby="dataset-preparation-title" className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-3">
            <h2 id="dataset-preparation-title" className={TYPOGRAPHY.headingMd}>
              Dataset preparation
            </h2>
            {readiness && !isError && !isLoading && (
              <Badge className="tracking-normal" variant={TIER_BADGE[readiness.tier].variant}>
                {TIER_BADGE[readiness.tier].label}
              </Badge>
            )}
          </div>
        </div>
        <Button
          onClick={onPrepare}
          disabled={
            isPreparing || isLoading || isError || !data || data.pair_count <= 0 || hasHandoff
          }
          aria-describedby={hasHandoff ? 'training-handoff-reminder' : undefined}
          aria-busy={isPreparing}
        >
          {isPreparing ? 'Preparing run…' : 'Prepare training run'}
        </Button>
      </div>

      {isLoading ? (
        <div role="status" className="space-y-4">
          <span className="sr-only">Checking dataset…</span>
          <div className="grid grid-cols-3 gap-4">
            {[0, 1, 2].map((index) => (
              <Skeleton key={index} className="h-16 w-full" />
            ))}
          </div>
          <Skeleton className="h-4 w-2/3" />
        </div>
      ) : isError || !data || !readiness ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 border-l-2 border-destructive bg-destructive-soft p-4 text-sm text-destructive"
        >
          <p>Failed to check dataset readiness. Try again to prepare a run.</p>
          <Button variant="secondary" onClick={() => void refetch()}>
            Retry readiness
          </Button>
        </div>
      ) : (
        <>
          <dl className="grid grid-cols-3 divide-x divide-border border-y border-border bg-surface py-4">
            {[
              ['Pairs', data.pair_count],
              ['Evaluations', data.evaluation_count],
              ['Reviewers', data.reviewer_count],
            ].map(([label, value]) => (
              <div
                key={label}
                className="flex flex-col gap-1 px-3 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3 sm:px-5"
              >
                <dt className="text-sm text-text-muted">{label}</dt>
                <dd className="text-xl font-semibold tabular-nums text-text">{value}</dd>
              </div>
            ))}
          </dl>
          <div className="space-y-4">
            <div
              role="note"
              className="space-y-1 border-l-2 border-warning pl-3 text-sm leading-relaxed text-text-muted"
            >
              <p>{SEEDED_DATA_NOTE}</p>
              {reviewerNote && <p>{reviewerNote}</p>}
            </div>
            {(readiness.tier !== 'reasonable' || comparison) && (
              <div className="space-y-1 text-sm leading-relaxed">
                {readiness.tier !== 'reasonable' && (
                  <p className="font-medium text-text">{readiness.message}</p>
                )}
                {comparison && <p className="text-text-muted">{comparison}</p>}
              </div>
            )}
            <details className="text-sm text-text-muted">
              <summary className="w-fit cursor-pointer rounded-sm font-medium text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                Dataset inclusion details
              </summary>
              <div className="mt-2 space-y-1 leading-relaxed">
                {readiness.tier === 'reasonable' && <p>{readiness.message}</p>}
                {(readiness.tier === 'small' || readiness.tier === 'reasonable') && (
                  <p>{RULE_OF_THUMB_NOTE}</p>
                )}
                <p>{describeFunnel(data.pair_count, data.skipped_counts)}</p>
              </div>
            </details>
          </div>
        </>
      )}
      {hasHandoff && (
        <p id="training-handoff-reminder" className="text-sm text-text-muted">
          Save the notebook URLs below before preparing another run.
        </p>
      )}
      {preparationError && (
        <p
          role="alert"
          className="border-l-2 border-destructive bg-destructive-soft p-3 text-sm text-destructive"
        >
          {preparationError}
        </p>
      )}
    </section>
  );
}
