import { CaretDown, MagnifyingGlass, Plus, UserMinus } from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import type { UserCounts } from './UserMetricsBar';

export type StatusFilter = 'all' | 'pending' | 'approved' | 'suspended' | 'rejected';
export type RoleFilter = 'all' | 'faculty' | 'admin';

interface UserFiltersToolbarProps {
  counts: UserCounts;
  statusFilter: StatusFilter;
  onStatusFilterChange: (status: StatusFilter) => void;
  roleFilter: RoleFilter;
  onRoleFilterChange: (role: RoleFilter) => void;
  searchQuery: string;
  onSearchQueryChange: (query: string) => void;
  selectedCount: number;
  onBulkDeactivate: () => void;
  isDeactivating?: boolean;
  onCreateFaculty: () => void;
}

export function UserFiltersToolbar({
  counts,
  statusFilter,
  onStatusFilterChange,
  roleFilter,
  onRoleFilterChange,
  searchQuery,
  onSearchQueryChange,
  selectedCount,
  onBulkDeactivate,
  isDeactivating,
  onCreateFaculty,
}: UserFiltersToolbarProps) {
  return (
    <>
      {/* Ledger Header Row 1: Status Filter Tabs */}
      <div className="border-b border-border bg-surface px-4 sm:px-6 py-3 overflow-x-auto">
        <div className="flex items-center gap-1.5 min-w-max">
          <button
            type="button"
            onClick={() => onStatusFilterChange('all')}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
              statusFilter === 'all'
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-surface text-text hover:bg-surface-subtle',
            )}
          >
            <span>All Users</span>
            <span
              className={cn(
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
                statusFilter === 'all'
                  ? 'bg-primary-foreground/20 text-primary-foreground'
                  : 'bg-surface-subtle text-text-muted',
              )}
            >
              {counts.all}
            </span>
          </button>

          <button
            type="button"
            onClick={() => onStatusFilterChange('pending')}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
              statusFilter === 'pending'
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-surface text-text hover:bg-surface-subtle',
            )}
          >
            <span>Pending Review</span>
            <span
              className={cn(
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
                statusFilter === 'pending'
                  ? 'bg-primary-foreground/20 text-primary-foreground'
                  : counts.pending > 0
                    ? 'bg-warning-soft text-warning border border-warning/30'
                    : 'bg-surface-subtle text-text-muted',
              )}
            >
              {counts.pending}
            </span>
          </button>

          <button
            type="button"
            onClick={() => onStatusFilterChange('approved')}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
              statusFilter === 'approved'
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-surface text-text hover:bg-surface-subtle',
            )}
          >
            <span>Active Accounts</span>
            <span
              className={cn(
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
                statusFilter === 'approved'
                  ? 'bg-primary-foreground/20 text-primary-foreground'
                  : 'bg-surface-subtle text-text-muted',
              )}
            >
              {counts.approved}
            </span>
          </button>

          <button
            type="button"
            onClick={() => onStatusFilterChange('suspended')}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
              statusFilter === 'suspended'
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-surface text-text hover:bg-surface-subtle',
            )}
          >
            <span>Suspended Accounts</span>
            <span
              className={cn(
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
                statusFilter === 'suspended'
                  ? 'bg-primary-foreground/20 text-primary-foreground'
                  : counts.suspended > 0
                    ? 'bg-destructive-soft text-destructive border border-destructive/30'
                    : 'bg-surface-subtle text-text-muted',
              )}
            >
              {counts.suspended}
            </span>
          </button>

          <button
            type="button"
            onClick={() => onStatusFilterChange('rejected')}
            className={cn(
              'inline-flex h-8 items-center gap-1.5 px-3 rounded-sm text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
              statusFilter === 'rejected'
                ? 'bg-primary text-primary-foreground'
                : 'border border-border bg-surface text-text hover:bg-surface-subtle',
            )}
          >
            <span>Rejected Accounts</span>
            <span
              className={cn(
                'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
                statusFilter === 'rejected'
                  ? 'bg-primary-foreground/20 text-primary-foreground'
                  : 'bg-surface-subtle text-text-muted',
              )}
            >
              {counts.rejected}
            </span>
          </button>
        </div>
      </div>

      {/* Ledger Header Row 2: Search, Role Selector & Action Buttons */}
      <div className="border-b border-border bg-surface-subtle/50 px-4 sm:px-6 py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 flex-1 max-w-lg">
          <div className="relative flex-1">
            <MagnifyingGlass
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 size-4 text-text-muted"
              aria-hidden="true"
            />
            <input
              type="text"
              className="h-10 w-full rounded-sm border border-input bg-surface pl-9 pr-3 text-xs sm:text-sm font-medium text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Search by name or email…"
              value={searchQuery}
              onChange={(e) => onSearchQueryChange(e.target.value)}
              aria-label="Search users"
            />
          </div>

          <div className="relative shrink-0">
            <select
              aria-label="Filter by role"
              value={roleFilter}
              onChange={(e) => onRoleFilterChange(e.target.value as RoleFilter)}
              className="h-10 appearance-none rounded-sm border border-input bg-surface pl-3.5 pr-9 text-xs sm:text-sm font-semibold text-text focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
            >
              <option value="all">All Roles</option>
              <option value="faculty">Faculty</option>
              <option value="admin">Admin</option>
            </select>
            <CaretDown
              className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 size-4 text-text-muted"
              aria-hidden="true"
            />
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {selectedCount > 0 ? (
            <button
              type="button"
              onClick={onBulkDeactivate}
              disabled={isDeactivating}
              className="inline-flex h-10 items-center gap-1.5 rounded-sm border border-destructive/30 bg-destructive-soft px-3.5 text-xs sm:text-sm font-semibold text-destructive hover:bg-destructive-soft/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive cursor-pointer disabled:opacity-50"
            >
              <UserMinus className="size-4" aria-hidden="true" />
              <span>Deactivate ({selectedCount})</span>
            </button>
          ) : null}

          <Button
            type="button"
            variant="primary"
            size="md"
            className="text-xs sm:text-sm h-10 px-4 font-semibold"
            onClick={onCreateFaculty}
          >
            <Plus className="size-4" aria-hidden="true" />
            <span>Create Faculty</span>
          </Button>
        </div>
      </div>
    </>
  );
}
