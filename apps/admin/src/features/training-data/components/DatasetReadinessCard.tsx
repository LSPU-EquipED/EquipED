import { ChartBar, Warning } from '@phosphor-icons/react';
import { Badge, CARD_STYLES, Skeleton } from '@equiped/ui';
import type { StatusVariant } from '@equiped/ui';
import { useDatasetReadiness } from '../hooks/useDatasetReadiness';
import { useTrainingJobs } from '../hooks/useTrainingJobs';
import type { LatestJobComparison, ReadinessTier } from '../utils/trainingData.utils';
import {
  compareToLatestJob,
  describeFunnel,
  getReadinessTier,
  getReviewerNote,
  RULE_OF_THUMB_NOTE,
  SEEDED_DATA_NOTE,
} from '../utils/trainingData.utils';

// The top tier is deliberately not the success color: volume alone has validated nothing.
const TIER_BADGE: Record<ReadinessTier, { label: string; variant: StatusVariant }> = {
  empty: { label: 'No pairs', variant: 'destructive' },
  'single-evaluation': { label: 'Single evaluation', variant: 'warning' },
  small: { label: 'Small', variant: 'warning' },
  reasonable: { label: 'Enough to try', variant: 'info' },
};

function describeComparison(comparison: LatestJobComparison): string | null {
  switch (comparison.kind) {
    case 'identical':
      return 'Dataset is identical to the latest job. Starting another job would freeze the same data again.';
    case 'changed':
      return `Changed since the latest job: ${comparison.from} → ${comparison.to} pairs.`;
    case 'unknown':
      return 'The latest job did not record its dataset, so it cannot be compared.';
    case 'no-jobs':
      return null;
  }
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs font-semibold text-text-muted">{label}</dt>
      <dd className="text-2xl font-semibold tabular-nums text-text">{value}</dd>
    </div>
  );
}

function ReadinessSkeleton() {
  return (
    <div role="status" className="space-y-4 p-6">
      <span className="sr-only">Checking dataset…</span>
      <div className="grid grid-cols-3 gap-4">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  );
}

export function DatasetReadinessCard({ agentId }: { agentId: string }) {
  const { data, isLoading, isError } = useDatasetReadiness(agentId);
  const { data: jobsData } = useTrainingJobs(agentId);
  const readiness = data ? getReadinessTier(data.pair_count, data.evaluation_count) : null;

  const header = (
    <div className={CARD_STYLES.header}>
      <div className="flex items-center gap-2">
        <ChartBar className="size-4 text-primary" aria-hidden="true" />
        <h2 className="text-xs font-bold uppercase tracking-wider text-text">Dataset Readiness</h2>
      </div>
      {readiness ? (
        <Badge variant={TIER_BADGE[readiness.tier].variant}>
          {TIER_BADGE[readiness.tier].label}
        </Badge>
      ) : null}
    </div>
  );

  if (isLoading) {
    return (
      <div className={CARD_STYLES.ledger}>
        {header}
        <ReadinessSkeleton />
      </div>
    );
  }

  if (isError || !data || !readiness) {
    return (
      <div className={CARD_STYLES.ledger}>
        {header}
        <div
          role="alert"
          className="flex items-center gap-2.5 bg-destructive-soft px-6 py-4 text-sm font-semibold text-destructive"
        >
          <Warning className="size-4 shrink-0" aria-hidden="true" />
          <span>Failed to check dataset readiness. Reload the page to try again.</span>
        </div>
      </div>
    );
  }

  const comparison = describeComparison(compareToLatestJob(data, jobsData?.jobs[0]));
  const reviewerNote = getReviewerNote(data.reviewer_count);
  const showRuleOfThumb = readiness.tier === 'small' || readiness.tier === 'reasonable';

  return (
    <div className={CARD_STYLES.ledger}>
      {header}
      <div className="space-y-4 p-6">
        <dl className="grid grid-cols-3 gap-4">
          <Stat label="Pairs" value={data.pair_count} />
          <Stat label="Evaluations" value={data.evaluation_count} />
          <Stat label="Reviewers" value={data.reviewer_count} />
        </dl>

        <div
          role="note"
          className="flex max-w-3xl gap-2.5 rounded-sm bg-warning-soft px-3 py-2.5 text-sm text-text"
        >
          <Warning className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
          <div className="space-y-1">
            <p>{SEEDED_DATA_NOTE}</p>
            {reviewerNote ? <p>{reviewerNote}</p> : null}
          </div>
        </div>

        <div className="max-w-3xl space-y-1">
          <p className="text-base font-semibold text-text">{readiness.message}</p>
          {showRuleOfThumb ? (
            <p className="text-sm text-text-muted">{RULE_OF_THUMB_NOTE}</p>
          ) : null}
          {comparison ? <p className="pt-3 text-sm text-text">{comparison}</p> : null}
        </div>

        <div className="border-t border-border pt-4">
          <p className="text-sm text-text-muted">
            {describeFunnel(data.pair_count, data.skipped_counts)}
          </p>
        </div>
      </div>
    </div>
  );
}
