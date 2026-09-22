import { CheckCircle, Warning } from '@phosphor-icons/react';
import type { AlignmentCheckSummary } from '../types';

interface AlignmentCheckMetricsProps {
  summary: AlignmentCheckSummary;
}

export function AlignmentCheckMetrics({ summary }: AlignmentCheckMetricsProps) {
  return (
    <div
      className="grid grid-cols-2 divide-x divide-y divide-border overflow-hidden rounded-md border border-border bg-surface sm:grid-cols-5 sm:divide-y-0 shadow-none"
      role="region"
      aria-label="Curriculum alignment metrics"
    >
      <div className="flex min-h-20 flex-col justify-between p-3.5 sm:p-4">
        <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
          <span>Match</span>
          <CheckCircle className="size-3.5 text-success" aria-hidden="true" />
        </div>
        <div className="mt-2">
          <span className="text-2xl font-semibold tabular-nums text-success">
            {summary.match}
          </span>
          <span className="ml-1 text-[11px] text-text-muted">objectives</span>
        </div>
      </div>

      <div className="flex min-h-20 flex-col justify-between p-3.5 sm:p-4">
        <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
          <span>Over-developed</span>
          <span className="size-2 rounded-full bg-info" aria-hidden="true" />
        </div>
        <div className="mt-2">
          <span className="text-2xl font-semibold tabular-nums text-info">
            {summary.over_developed}
          </span>
          <span className="ml-1 text-[11px] text-text-muted">exceeds</span>
        </div>
      </div>

      <div className="flex min-h-20 flex-col justify-between p-3.5 sm:p-4">
        <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
          <span>Under-developed</span>
          <Warning className="size-3.5 text-warning" aria-hidden="true" />
        </div>
        <div className="mt-2">
          <span className="text-2xl font-semibold tabular-nums text-warning">
            {summary.under_developed}
          </span>
          <span className="ml-1 text-[11px] text-text-muted">needs depth</span>
        </div>
      </div>

      <div className="flex min-h-20 flex-col justify-between p-3.5 sm:p-4">
        <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
          <span>Not addressed</span>
          <span className="size-2 rounded-full bg-destructive" aria-hidden="true" />
        </div>
        <div className="mt-2">
          <span className="text-2xl font-semibold tabular-nums text-destructive">
            {summary.not_addressed}
          </span>
          <span className="ml-1 text-[11px] text-text-muted">missing</span>
        </div>
      </div>

      <div className="flex min-h-20 flex-col justify-between p-3.5 sm:p-4">
        <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
          <span>Not observed</span>
          <span className="size-2 rounded-full bg-border-strong" aria-hidden="true" />
        </div>
        <div className="mt-2">
          <span className="text-2xl font-semibold tabular-nums text-text-muted">
            {summary.not_observed ?? 0}
          </span>
          <span className="ml-1 text-[11px] text-text-muted">unverified</span>
        </div>
      </div>
    </div>
  );
}
