import { Clock, UserCheck, UserMinus, Users, type Icon } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';
import { Skeleton } from '@/shared/components/Skeleton';
export interface UserCounts {
  all: number;
  pending: number;
  approved: number;
  suspended: number;
  rejected: number;
}

interface MetricItemProps {
  label: string;
  value: number;
  sublabel: string;
  icon: Icon;
  variant?: 'default' | 'warning' | 'destructive';
  isLoading: boolean;
}
function MetricItem({
  label,
  value,
  sublabel,
  icon: IconComponent,
  variant = 'default',
  isLoading,
}: MetricItemProps) {
  const isWarning = variant === 'warning' && value > 0;
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
              : isWarning
                ? 'bg-warning-soft text-warning border-warning/25'
                : 'bg-surface-subtle text-text-muted border-border',
          )}
          aria-hidden="true"
        >
          <IconComponent className="size-3.5" />
        </div>
      </div>

      <div className="mt-3">
        <p
          className={cn(
            'text-2xl font-bold tabular-nums tracking-tight',
            isDestructive ? 'text-destructive' : isWarning ? 'text-warning' : 'text-text',
          )}
        >
          {isLoading ? <Skeleton className="h-8 w-16" /> : value.toLocaleString()}
        </p>
        <p className="text-[11px] text-text-muted mt-0.5 font-medium">{sublabel}</p>
      </div>
    </div>
  );
}
interface UserMetricsBarProps {
  counts: UserCounts;
  isLoading: boolean;
}
export function UserMetricsBar({ counts, isLoading }: UserMetricsBarProps) {
  return (
    <div aria-busy={isLoading} className="border border-border bg-surface rounded-md overflow-hidden shadow-none">
      <div className="grid grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-border">
        <MetricItem
          label="Total Users"
          value={counts.all}
          sublabel="Registered accounts"
          icon={Users}
          isLoading={isLoading}
        />
        <MetricItem
          label="Active Faculty"
          value={counts.approved}
          sublabel="Authorized educators"
          icon={UserCheck}
          isLoading={isLoading}
        />
        <MetricItem
          label="Pending Approvals"
          value={counts.pending}
          sublabel={counts.pending > 0 ? 'Requires admin review' : 'No pending requests'}
          icon={Clock}
          variant="warning"
          isLoading={isLoading}
        />
        <MetricItem
          label="Suspended Accounts"
          value={counts.suspended}
          sublabel={counts.suspended > 0 ? 'Access restricted' : 'All accounts in good standing'}
          icon={UserMinus}
          variant="destructive"
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
