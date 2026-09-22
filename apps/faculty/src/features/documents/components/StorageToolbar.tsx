import { ArrowCounterClockwise, SlidersHorizontal, SortAscending } from '@phosphor-icons/react';
import { cn, Dropdown } from '@equiped/ui';
import type { DocumentSortOption, StorageProgramFilter, StorageStatusFilter } from '../utils/storage.utils';

export type { DocumentSortOption };


interface StorageToolbarProps {
  programFilter: StorageProgramFilter;
  setProgramFilter: (val: StorageProgramFilter) => void;
  statusFilter: StorageStatusFilter;
  setStatusFilter: (val: StorageStatusFilter) => void;
  sortOption?: DocumentSortOption;
  setSortOption?: (val: DocumentSortOption) => void;
  totalModules?: number;
  bscsCount?: number;
  bsInfoTechCount?: number;
  onResetFilters?: () => void;
}

export function StorageToolbar({
  programFilter,
  setProgramFilter,
  statusFilter,
  setStatusFilter,
  sortOption = 'uploaded-desc',
  setSortOption,
  totalModules,
  bscsCount,
  bsInfoTechCount,
  onResetFilters,
}: StorageToolbarProps) {
  const hasActiveFilters = programFilter !== 'ALL' || statusFilter !== 'all';

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-y border-border bg-surface px-4 py-3 sm:px-6">
      {/* ── Left: Program Pills ────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-xs font-medium text-text-muted">Program</span>
        <div
          role="tablist"
          aria-label="Filter modules by academic program"
          className="flex flex-wrap items-center gap-1.5"
        >
          {([
            { id: 'ALL' as const, label: 'All Modules', count: totalModules },
            { id: 'BSCS' as const, label: 'BSCS', count: bscsCount },
            { id: 'BSInfoTech' as const, label: 'BSInfoTech', count: bsInfoTechCount },
          ] as const).map((tab) => {
            const isActive = programFilter === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => setProgramFilter(tab.id)}
                className={cn(
                  'inline-flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-sm border px-3 text-xs font-medium transition-colors cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
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

        {/* Clear Filters Button (Visible when filters are active) */}
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

      {/* ── Right: Filter & Sorter Controls ────────────────────────── */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 xl:ml-auto">
        {/* Sorter Dropdown */}
        {setSortOption ? (
          <Dropdown
            id="storage-sort-select"
            aria-label="Sort documents"
            label="Sort:"
            size="md"
            align="right"
            inlineLabel
            icon={<SortAscending className="size-3.5" />}
            value={sortOption}
            onChange={(val) => setSortOption(val as DocumentSortOption)}
            options={[
              { value: 'uploaded-desc', label: 'Newest Uploaded' },
              { value: 'uploaded-asc', label: 'Oldest Uploaded' },
              { value: 'title-asc', label: 'Title (A–Z)' },
              { value: 'title-desc', label: 'Title (Z–A)' },
              { value: 'course-asc', label: 'Course Code' },
              { value: 'pages-desc', label: 'Page Count' },
            ]}
          />
        ) : null}

        {/* Status Filter Dropdown */}
        <Dropdown
          id="storage-status-filter"
          aria-label="Filter by status"
          label="Status:"
          size="md"
          align="right"
          inlineLabel
          icon={<SlidersHorizontal className="size-3.5" />}
          value={statusFilter}
          onChange={(val) => setStatusFilter(val as StorageStatusFilter)}
          options={[
            { value: 'all', label: 'All Statuses' },
            { value: 'PROCESSED', label: 'Evaluated' },
            { value: 'PROCESSING', label: 'Processing' },
            { value: 'FAILED', label: 'Failed' },
          ]}
        />
      </div>
    </div>
  );
}
