import { MagnifyingGlass } from '@phosphor-icons/react';
import { Dropdown } from '@equiped/ui';
import type { HistoryRoleTab } from '../constants';

const STATUS_OPTIONS = [
  { value: 'all', label: 'All statuses' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'IN_PROGRESS', label: 'In progress' },
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
    <div className="grid min-w-0 gap-4 border-b border-border bg-surface px-4 py-4 sm:px-6 xl:grid-cols-[minmax(0,1fr)_minmax(16rem,24rem)] xl:items-end">
      <div className="grid min-w-0 gap-3 sm:grid-cols-[minmax(0,1fr)_9rem_auto] sm:items-end">
        {allowedRoleTabs.length > 1 ? (
          <Dropdown
            id="history-role-filter"
            aria-label="Specialist"
            label="Specialist"
            size="sm"
            containerClassName="min-w-0"
            className="w-full min-w-0"
            value={activeRole}
            onChange={(value) => onRoleChange(String(value))}
            options={allowedRoleTabs.map((tab) => ({
              value: tab.id,
              label: tab.label,
            }))}
          />
        ) : (
          <div className="min-w-0">
            <p className="text-xs font-medium text-text-muted">Specialist</p>
            <p className="mt-1.5 flex min-h-8 items-center text-xs font-medium text-text">
              {allowedRoleTabs.find((tab) => tab.id === activeRole)?.label ??
                activeRole}
            </p>
          </div>
        )}

        <Dropdown
          id="history-status-filter"
          aria-label="Status"
          label="Status"
          size="sm"
          containerClassName="min-w-0"
          className="w-full min-w-0"
          value={status}
          onChange={(value) => onStatusChange(String(value))}
          options={[...STATUS_OPTIONS]}
        />

        {hasActiveFilters ? (
          <button
            type="button"
            onClick={onResetFilters}
            className="inline-flex min-h-8 w-fit items-center text-xs font-semibold text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            Reset
          </button>
        ) : null}
      </div>

      <div className="min-w-0">
        <div className="mb-1.5 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <label
            htmlFor="history-search"
            className="text-xs font-medium text-text-muted"
          >
            Search this page
          </label>
          <div
            className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-text-muted"
            aria-live="polite"
          >
            <span className="tabular-nums">
              {isLoading && !hasData
                ? 'Loading…'
                : `${total} evaluation${total === 1 ? '' : 's'} found`}
            </span>
            {isFetching && hasData ? (
              <span role="status">Updating…</span>
            ) : null}
          </div>
        </div>
        <div className="relative min-w-0">
          <MagnifyingGlass
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-text-muted"
            aria-hidden="true"
          />
          <input
            id="history-search"
            type="text"
            placeholder="Module title or evaluation ID…"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            className="h-8 w-full rounded-sm border border-input bg-surface pl-8 pr-3 text-xs text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label="Search evaluations"
          />
        </div>
      </div>
    </div>
  );
}
