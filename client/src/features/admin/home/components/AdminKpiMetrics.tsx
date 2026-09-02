import {
  ClipboardText,
  Clock,
  Files,
  Users,
  type Icon,
} from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';
import { Skeleton } from '@/shared/components/Skeleton';
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
    <div className="flex flex-col justify-between p-4 sm:p-5 bg-surface transition-colors">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-text-muted select-none">
          {label}
        </span>
        <div
          className={cn(
            'flex size-7 items-center justify-center rounded-sm shrink-0 border',
            isDestructive
              ? 'bg-destructive-soft text-destructive border-destructive/25'
              : 'bg-surface-subtle text-text-muted border-border',
          )}
          aria-hidden="true"
        >
          <IconComponent className="size-3.5" />
        </div>
      </div>

      <div className="mt-3">
        {isLoading ? (
          <div className="space-y-2" role="status" aria-label="Loading metric">
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-2.5 w-32 max-w-full" />
          </div>
        ) : isError ? (
          <p className="text-xs font-semibold text-destructive">Failed to load</p>
        ) : (
          <p
            className={cn(
              'text-2xl font-bold tabular-nums tracking-tight',
              isDestructive ? 'text-destructive' : 'text-text',
            )}
          >
            {value.toLocaleString()}
          </p>
        )}
        <p className="text-[11px] text-text-muted mt-0.5 font-medium">{sublabel}</p>
      </div>
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
    <div className="border border-border bg-surface rounded-md overflow-hidden shadow-none">
      <div className="grid grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-border">
        <SummaryItem
          label="Total SLMs Processed"
          value={summary?.total_documents ?? 0}
          sublabel="Cataloged course modules"
          icon={Files}
          isLoading={isLoading}
          isError={isError}
        />
        <SummaryItem
          label="Active Evaluations"
          value={summary?.active_evaluations ?? 0}
          sublabel="Currently in evaluation queue"
          icon={Clock}
          isLoading={isLoading}
          isError={isError}
        />
        <SummaryItem
          label="Registered Faculty"
          value={summary?.total_faculty ?? 0}
          sublabel="Verified faculty instructors"
          icon={Users}
          isLoading={isLoading}
          isError={isError}
        />
        <SummaryItem
          label="Failed Evaluations"
          value={summary?.failed_evaluations ?? 0}
          sublabel="Processing or alignment failures"
          icon={ClipboardText}
          isLoading={isLoading}
          isError={isError}
          variant="destructive"
        />
      </div>
    </div>
  );
}
