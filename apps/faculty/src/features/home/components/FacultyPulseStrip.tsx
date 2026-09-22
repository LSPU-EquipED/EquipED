import { Books, CheckCircle, Clock, Warning } from '@phosphor-icons/react';
import { Skeleton } from '@equiped/ui';
import type { DocumentStats } from '@equiped/types';

export function FacultyPulseStrip({ stats, isLoading }: { stats: DocumentStats; isLoading: boolean }) {
  const metrics = [
    {
      label: 'Total modules',
      value: stats.total,
      detail: 'In your repository',
      color: 'text-text',
      icon: Books,
      iconColor: 'text-text-muted',
    },
    {
      label: 'Extracted',
      value: stats.ready,
      detail: 'Document processing complete',
      color: 'text-text',
      icon: CheckCircle,
      iconColor: 'text-success',
    },
    {
      label: 'Processing',
      value: stats.processing,
      detail: 'Intake or cleanup in progress',
      color: 'text-info',
      icon: Clock,
      iconColor: 'text-info',
    },
    {
      label: 'Failed uploads',
      value: stats.failed,
      detail: 'Document processing failed',
      color: stats.failed ? 'text-destructive' : 'text-text',
      icon: Warning,
      iconColor: stats.failed ? 'text-destructive' : 'text-text-muted',
    },
  ];

  return (
    <dl
      aria-label="Module overview"
      className="grid grid-cols-2 divide-x divide-y divide-border overflow-hidden rounded-md border border-border bg-surface sm:grid-cols-4 sm:divide-y-0 shadow-none"
    >
      {metrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <div key={metric.label} className="flex min-h-22 flex-col justify-between p-4 sm:p-5">
            <div className="flex items-center justify-between gap-1.5 text-xs font-medium text-text-muted">
              <dt className="text-xs font-medium text-text-muted">{metric.label}</dt>
              <Icon className={`size-3.5 shrink-0 ${metric.iconColor}`} aria-hidden="true" />
            </div>
            <dd className="mt-3">
              {isLoading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <span className={`text-2xl sm:text-[28px] font-semibold leading-tight tabular-nums ${metric.color}`}>
                  {metric.value.toLocaleString()}
                </span>
              )}
              <span className="mt-1 block text-xs text-text-muted">{metric.detail}</span>
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
