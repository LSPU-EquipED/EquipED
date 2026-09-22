import { MagnifyingGlass } from '@phosphor-icons/react';
import { Dropdown } from '@equiped/ui';
import type { HistoryRoleTab } from '../constants';

const STATUS_OPTIONS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'IN_PROGRESS', label: 'In Progress' },
  { value: 'FAILED', label: 'Failed' },
] as const;

interface HistoryFiltersProps {
  allowedRoleTabs: readonly HistoryRoleTab[];
  activeRole: string;
  onRoleChange: (role: string) => void;
  status: string;
  onStatusChange: (status: string) => void;
  search: string;
  onSearchChange: (search: string) => void;
  hasActiveFilters: boolean;
  onResetFilters: () => void;
  isLoading: boolean;
  isFetching: boolean;
  hasData: boolean;
  total: number;
}

export function HistoryFilters({
  allowedRoleTabs,
  activeRole,
  onRoleChange,
  status,
  onStatusChange,
  search,
  onSearchChange,
  hasActiveFilters,
  onResetFilters,
  isLoading,
  isFetching,
  hasData,
  total,
}: HistoryFiltersProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-border bg-surface px-4 py-3 sm:px-6">
      <div className="flex flex-wrap items-center gap-3">
        {allowedRoleTabs.length > 1 && (
          <Dropdown
            id="history-role-filter"
            aria-label="Role"
            label="Role:"
            inlineLabel
            size="sm"
            value={activeRole}
            onChange={(value) => onRoleChange(String(value))}
            options={allowedRoleTabs.map((tab) => ({ value: tab.id, label: tab.label }))}
          />
        )}

        <Dropdown
          id="history-status-filter"
          aria-label="Status"
          label="Status:"
          inlineLabel
          size="sm"
          value={status}
          onChange={(value) => onStatusChange(String(value))}
          options={[...STATUS_OPTIONS]}
        />

        {hasActiveFilters ? (
          <button
            type="button"
            onClick={onResetFilters}
            className="cursor-pointer text-xs font-semibold text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            Reset
          </button>
        ) : null}
      </div>

      <div className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-3 sm:justify-end">
        <div className="relative min-w-[12rem] flex-1 sm:max-w-sm">
          <MagnifyingGlass
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-text-muted"
            aria-hidden="true"
          />
          <input
            type="text"
            placeholder="Search this page by title or ID…"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            className="h-8 w-full rounded-sm border border-input bg-surface pl-8 pr-3 text-xs text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label="Search evaluations"
          />
        </div>

        <div className="flex items-center gap-2.5" aria-live="polite">
          <span className="whitespace-nowrap text-xs font-semibold tabular-nums text-text-muted">
            {isLoading && !hasData ? 'Loading…' : `${total} evaluation${total === 1 ? '' : 's'} found`}
          </span>
          {isFetching && hasData ? (
            <span role="status" className="text-xs text-text-muted">Updating…</span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
