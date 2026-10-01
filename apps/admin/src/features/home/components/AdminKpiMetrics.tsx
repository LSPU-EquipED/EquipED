import {
  Warning,
  Clock,
  Files,
  Users,
  type Icon,
} from '@phosphor-icons/react';
import { cn, Skeleton } from '@equiped/ui';
import type { SystemSummaryResponse } from '../types';

interface SummaryItemProps {
  label: string;
  value: number;
  sublabel: string;
  icon: Icon;
  isLoading: boolean;
  isError: boolean;
  variant?: 'default' | 'destructive';
}

function SummaryItem({
  label,
  value,
  sublabel,
  icon: IconComponent,
  isLoading,
  isError,
  variant = 'default',
}: SummaryItemProps) {
  const isDestructive = variant === 'destructive' && value > 0;

  return (
    <div className="flex min-w-0 flex-col justify-between p-4 sm:p-5 bg-surface transition-colors">
      <div className="flex items-center justify-between gap-2">
        <dt className="text-xs font-medium leading-5 text-text-muted">
          {label}
        </dt>
        <div
          className={cn(
            'flex size-7 items-center justify-center rounded-sm shrink-0 border transition-colors',
            isDestructive
              ? 'bg-destructive-soft text-destructive border-destructive/25'
              : 'bg-surface-subtle/50 text-text-muted border-border/70',
          )}
          aria-hidden="true"
        >
          <IconComponent className="size-3.5" />
        </div>
      </div>

      <dd className="mt-3">
        {isLoading ? (
          <div role="status" aria-label="Loading metric">
            <Skeleton className="h-6 w-16" />
          </div>
        ) : isError ? (
          <p className="text-xs font-medium text-destructive">Failed to load</p>
        ) : (
          <p
            className={cn(
              'text-2xl font-semibold leading-none tabular-nums',
              isDestructive ? 'text-destructive' : 'text-text',
            )}
          >
            {value.toLocaleString()}
          </p>
        )}
        <span className="mt-2 block text-xs leading-5 text-text-muted">
          {sublabel}
        </span>
      </dd>
    </div>
  );
}

export function AdminKpiMetrics({
  summary,
  isLoading,
  isError,
}: {
  summary?: SystemSummaryResponse;
  isLoading: boolean;
  isError: boolean;
}) {
  return (
    <dl
      aria-label="System overview"
      className="grid grid-cols-2 sm:grid-cols-4 gap-px border-border overflow-hidden rounded-md border border-border bg-border shadow-none"
    >
      <SummaryItem
        label="Total modules"
        value={summary?.total_documents ?? 0}
        sublabel="Cataloged course modules"
        icon={Files}
        isLoading={isLoading}
        isError={isError}
      />
      <SummaryItem
        label="Active evaluations"
        value={summary?.active_evaluations ?? 0}
        sublabel="Currently in evaluation queue"
        icon={Clock}
        isLoading={isLoading}
        isError={isError}
      />
      <SummaryItem
        label="Registered faculty"
        value={summary?.total_faculty ?? 0}
        sublabel="Faculty accounts"
        icon={Users}
        isLoading={isLoading}
        isError={isError}
      />
      <SummaryItem
        label="Failed evaluations"
        value={summary?.failed_evaluations ?? 0}
        sublabel="Evaluation runs that failed"
        icon={Warning}
        isLoading={isLoading}
        isError={isError}
        variant="destructive"
      />
    </dl>
  );
}
