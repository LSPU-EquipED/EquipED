import { Funnel } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';

export const ACTION_FILTERS = [
  { id: 'all', label: 'All Actions' },
  { id: 'EDIT', label: 'Score Overrides (EDIT)' },
  { id: 'ACCEPT', label: 'Approved (ACCEPT)' },
  { id: 'REJECT', label: 'Rejections (REJECT)' },
] as const;

interface PreferenceLogFiltersProps {
  actionFilter: string;
  onFilterChange: (filterId: string) => void;
  totalRecords: number;
}

export function PreferenceLogFilters({
  actionFilter,
  onFilterChange,
  totalRecords,
}: PreferenceLogFiltersProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs font-semibold text-text-muted mr-1.5 inline-flex items-center gap-1">
          <Funnel className="size-3 text-text-muted" />
          <span>Filter:</span>
        </span>
        <div className="inline-flex flex-wrap items-center gap-1 rounded-sm bg-surface-subtle p-1 border border-border">
          {ACTION_FILTERS.map((f) => {
            const isSelected = actionFilter === f.id;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => onFilterChange(f.id)}
                className={cn(
                  'rounded-xs px-3 py-1 text-xs font-semibold transition-colors cursor-pointer select-none border',
                  isSelected
                    ? 'border-primary bg-primary text-primary-foreground font-bold shadow-2xs'
                    : 'border-transparent text-text-muted hover:text-text',
                )}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      <span className="text-xs font-mono font-semibold text-text-muted tabular-nums">
        {totalRecords} audit records logged
      </span>
    </div>
  );
}
