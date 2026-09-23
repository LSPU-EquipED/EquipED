import { ArrowCounterClockwise, SlidersHorizontal } from '@phosphor-icons/react';
import { cn, Dropdown } from '@equiped/ui';
import type { UserCounts } from '../types';

export type StatusFilter = 'all' | 'pending' | 'approved' | 'suspended' | 'rejected';
export type RoleFilter = 'all' | 'faculty' | 'admin';

interface UserFiltersToolbarProps {
  counts: UserCounts;
  statusFilter: StatusFilter;
  onStatusFilterChange: (status: StatusFilter) => void;
  roleFilter: RoleFilter;
  onRoleFilterChange: (role: RoleFilter) => void;
  hasActiveFilters?: boolean;
  onResetFilters?: () => void;
}

export function UserFiltersToolbar({
  counts,
  statusFilter,
  onStatusFilterChange,
  roleFilter,
  onRoleFilterChange,
  hasActiveFilters,
  onResetFilters,
}: UserFiltersToolbarProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-y border-border bg-surface px-4 py-3 sm:px-6">
      {/* ── Left: Status Filter Pills (matching StorageToolbar) ─────── */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-xs font-medium text-text-muted">Status</span>
        <div
          role="tablist"
          aria-label="Filter users by account status"
          className="flex flex-wrap items-center gap-1.5"
        >
          {([
            { id: 'all' as const, label: 'All Users', count: counts.all },
            { id: 'pending' as const, label: 'Pending Review', count: counts.pending },
            { id: 'approved' as const, label: 'Active Accounts', count: counts.approved },
            { id: 'suspended' as const, label: 'Suspended Accounts', count: counts.suspended },
            { id: 'rejected' as const, label: 'Rejected Accounts', count: counts.rejected },
          ] as const).map((tab) => {
            const isActive = statusFilter === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => onStatusFilterChange(tab.id)}
                className={cn(
                  'inline-flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-sm border px-3 text-xs font-medium transition-colors cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  isActive
                    ? 'border-primary/30 bg-primary-soft text-primary'
                    : 'border-transparent text-text-muted hover:border-border hover:bg-surface-subtle hover:text-text',
                )}
              >
                <span>{tab.label}</span>
                {tab.count != null ? (
                  <span
                    className={cn(
                      'inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-xs px-1.5 text-[11px] tabular-nums font-semibold leading-5',
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-surface-subtle text-text-muted',
                    )}
                  >
                    {tab.count}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>

        {/* Reset Filters Button */}
        {hasActiveFilters && onResetFilters ? (
          <button
            type="button"
            onClick={onResetFilters}
            className="inline-flex h-8 items-center gap-1 rounded-sm px-2 text-xs font-medium text-text-muted transition-colors hover:bg-destructive-soft/50 hover:text-destructive cursor-pointer"
            title="Reset filters"
          >
            <ArrowCounterClockwise className="size-3" aria-hidden="true" />
            <span>Reset</span>
          </button>
        ) : null}
      </div>

      {/* ── Right: Role Filter Dropdown ────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 xl:ml-auto">
        <Dropdown
          id="user-role-filter"
          aria-label="Filter by role"
          label="Role:"
          size="md"
          align="right"
          inlineLabel
          icon={<SlidersHorizontal className="size-3.5" />}
          value={roleFilter}
          onChange={(val) => onRoleFilterChange(val as RoleFilter)}
          options={[
            { value: 'all', label: 'All Roles' },
            { value: 'faculty', label: 'Faculty' },
            { value: 'admin', label: 'Admin' },
          ]}
        />
      </div>
    </div>
  );
}
