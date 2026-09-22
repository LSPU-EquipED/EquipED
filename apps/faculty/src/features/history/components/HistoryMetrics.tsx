import { CheckCircle, Clock, ListChecks, Timer } from '@phosphor-icons/react';
import { Skeleton } from '@equiped/ui';
import type { EvaluationListStats, HistoryEvaluationItem } from '../types';

interface HistoryMetricsProps {
  isLoading: boolean;
  hasData: boolean;
  total: number;
  stats?: EvaluationListStats;
  items: HistoryEvaluationItem[];
}

function calculateCompletedCount(stats?: EvaluationListStats, items: HistoryEvaluationItem[] = []) {
  if (stats) return stats.completed;
  return items.filter((item) => item.status?.toUpperCase().startsWith('COMPLETED')).length;
}

function calculateInProgressCount(stats?: EvaluationListStats, items: HistoryEvaluationItem[] = []) {
  if (stats) return stats.in_progress;
  return items.filter((item) =>
    ['EVALUATING', 'PREPROCESSING', 'SYNTHESIZING', 'SUBMITTED', 'QUEUED'].includes(
      item.status?.toUpperCase(),
    ),
  ).length;
}

function calculateAvgDuration(stats?: EvaluationListStats, items: HistoryEvaluationItem[] = []) {
  if (stats) {
    if (typeof stats.average_duration_seconds === 'number') {
      const avg = Math.round(stats.average_duration_seconds);
      const mins = Math.floor(avg / 60);
      const secs = avg % 60;
      if (mins > 0) return `${mins}m ${secs}s`;
      return `${secs}s`;
    }
    return '—';
  }
  const durations = items
    .map((item) => {
      if (typeof item.duration_seconds === 'number' && item.duration_seconds > 0) {
        return item.duration_seconds;
      }
      if (item.submitted_at && item.completed_at) {
        const diff = (new Date(item.completed_at).getTime() - new Date(item.submitted_at).getTime()) / 1000;
        return diff > 0 ? diff : null;
      }
      return null;
    })
    .filter((d): d is number => d !== null);

  if (durations.length === 0) return '—';
  const avg = Math.round(durations.reduce((a, b) => a + b, 0) / durations.length);
  const mins = Math.floor(avg / 60);
  const secs = avg % 60;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

export function HistoryMetrics({
  isLoading,
  hasData,
  total,
  stats,
  items,
}: HistoryMetricsProps) {
  const displayTotal = stats ? stats.total : total;
  const completedCount = calculateCompletedCount(stats, items);
  const inProgressCount = calculateInProgressCount(stats, items);
  const avgDurationStr = calculateAvgDuration(stats, items);

  return (
    <div
      className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4"
      role="region"
      aria-label="Evaluation log metrics"
    >
      <div className="flex flex-col justify-between rounded-sm border border-border bg-surface p-3.5 sm:p-4">
        <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
          <span>Total Runs</span>
          <ListChecks className="size-4 text-primary" aria-hidden="true" />
        </div>
        <div className="mt-2.5">
          {isLoading && !hasData ? (
            <Skeleton className="h-7 w-12" />
          ) : (
            <>
              <span className="text-2xl font-semibold tabular-nums text-text">
                {displayTotal}
              </span>
              <span className="ml-1.5 text-xs text-text-muted">evaluations</span>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-col justify-between rounded-sm border border-border bg-surface p-3.5 sm:p-4">
        <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
          <span>Completed</span>
          <CheckCircle className="size-4 text-success" aria-hidden="true" />
        </div>
        <div className="mt-2.5">
          {isLoading && !hasData ? (
            <Skeleton className="h-7 w-12" />
          ) : (
            <>
              <span className="text-2xl font-semibold tabular-nums text-success">
                {completedCount}
              </span>
              <span className="ml-1.5 text-xs text-text-muted">verified</span>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-col justify-between rounded-sm border border-border bg-surface p-3.5 sm:p-4">
        <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
          <span>In Progress</span>
          <Clock className="size-4 text-info" aria-hidden="true" />
        </div>
        <div className="mt-2.5">
          {isLoading && !hasData ? (
            <Skeleton className="h-7 w-12" />
          ) : (
            <>
              <span className="text-2xl font-semibold tabular-nums text-info">
                {inProgressCount}
              </span>
              <span className="ml-1.5 text-xs text-text-muted">active</span>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-col justify-between rounded-sm border border-border bg-surface p-3.5 sm:p-4">
        <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
          <span>Avg Run Time</span>
          <Timer className="size-4 text-text-muted" aria-hidden="true" />
        </div>
        <div className="mt-2.5">
          {isLoading && !hasData ? (
            <Skeleton className="h-7 w-12" />
          ) : (
            <>
              <span className="text-2xl font-semibold tabular-nums text-text">
                {avgDurationStr}
              </span>
              <span className="ml-1.5 text-xs text-text-muted">per evaluation</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
