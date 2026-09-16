import { Books, CheckCircle, Clock, Warning } from '@phosphor-icons/react';
import { Skeleton, cn } from '@equiped/ui';

export interface FacultyPulseStripProps {
  totalModules?: number;
  readyModules?: number;
  inProgressCount?: number;
  actionRequiredCount?: number;
  isLoading?: boolean;
  onSelectFilter?: (filter: 'all' | 'ready' | 'processing' | 'action_required') => void;
  activeFilter?: 'all' | 'ready' | 'processing' | 'action_required';
}

export function FacultyPulseStrip({
  totalModules = 0,
  readyModules = 0,
  inProgressCount = 0,
  actionRequiredCount = 0,
  isLoading = false,
  onSelectFilter,
  activeFilter = 'all',
}: FacultyPulseStripProps) {
  const items = [
    {
      id: 'all' as const,
      label: 'Total Modules',
      count: totalModules,
      subtitle: 'Course SLMs in repository',
      icon: Books,
      iconContainer: 'bg-primary/10 border-primary/20 text-primary',
      countClass: 'text-text',
    },
    {
      id: 'ready' as const,
      label: 'Ready for Review',
      count: readyModules,
      subtitle: 'Completed intake & ready',
      icon: CheckCircle,
      iconContainer: 'bg-success-soft border-success/20 text-success',
      countClass: 'text-success',
    },
    {
      id: 'processing' as const,
      label: 'In Ingestion',
      count: inProgressCount,
      subtitle: 'Parsing syllabus & content',
      icon: Clock,
      iconContainer: 'bg-info-soft border-info/20 text-info',
      countClass: 'text-info',
    },
    {
      id: 'action_required' as const,
      label: 'Action Required',
      count: actionRequiredCount,
      subtitle:
        actionRequiredCount > 0
          ? 'Flagged items requiring review'
          : 'All modules verified clean',
      icon: Warning,
      iconContainer:
        actionRequiredCount > 0
          ? 'bg-warning-soft border-warning/20 text-warning'
          : 'bg-surface-subtle border-border text-text-muted',
      countClass: actionRequiredCount > 0 ? 'text-warning' : 'text-text-muted',
    },
  ];

  return (
    <div
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      role="region"
      aria-label="Repository pulse metrics"
    >
      {items.map((item) => {
        const IconComponent = item.icon;
        const isSelected = activeFilter === item.id;
        const isClickable = Boolean(onSelectFilter);

        return (
          <div
            key={item.id}
            onClick={isClickable ? () => onSelectFilter?.(item.id) : undefined}
            onKeyDown={
              isClickable
                ? (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectFilter?.(item.id);
                    }
                  }
                : undefined
            }
            tabIndex={isClickable ? 0 : undefined}
            role={isClickable ? 'button' : undefined}
            aria-pressed={isClickable ? isSelected : undefined}
            className={cn(
              'rounded-md border bg-surface p-5 flex flex-col justify-between gap-3 transition-colors select-none',
              isSelected ? 'border-primary ring-1 ring-primary/30' : 'border-border',
              isClickable &&
                'cursor-pointer hover:border-primary/40 hover:bg-surface-subtle/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-text-muted">{item.label}</span>
              <div
                className={cn(
                  'flex size-8 items-center justify-center rounded-sm border shrink-0',
                  item.iconContainer,
                )}
                aria-hidden="true"
              >
                <IconComponent className="size-4" />
              </div>
            </div>

            <div>
              {isLoading ? (
                <div className="space-y-1.5" role="status" aria-label={`Loading ${item.label}`}>
                  <Skeleton className="h-8 w-16" />
                  <Skeleton className="h-3.5 w-32" />
                </div>
              ) : (
                <>
                  <p
                    className={cn(
                      'text-2xl font-bold tracking-tight tabular-nums',
                      item.countClass,
                    )}
                  >
                    {item.count.toLocaleString()}
                  </p>
                  <p
                    className={cn(
                      'text-xs mt-1 leading-normal font-normal',
                      item.id === 'action_required' && actionRequiredCount > 0
                        ? 'text-warning font-medium'
                        : 'text-text-muted',
                    )}
                  >
                    {item.subtitle}
                  </p>
                </>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
