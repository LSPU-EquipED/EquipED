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
    <div className="rounded-md border border-border bg-surface px-4 sm:px-6 py-2.5 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-none">
      {/* ── Left: Program Pills ────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2">
        <div
          role="tablist"
          aria-label="Filter modules by academic program"
          className="flex items-center gap-1.5"
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
                  'inline-flex items-center rounded-sm px-3 py-1.5 text-xs font-semibold transition-all cursor-pointer select-none',
                  isActive
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : 'text-text-muted hover:text-text hover:bg-surface-subtle border border-transparent hover:border-border font-medium',
                )}
              >
                <span>{tab.label}</span>
                {tab.count != null ? (
                  <span
                    className={cn(
                      'ml-1.5 inline-flex items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-mono tabular-nums font-bold leading-none',
                      isActive
                        ? 'bg-white/20 text-white'
                        : 'bg-surface-subtle border border-border/80 text-text-muted',
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
            className="inline-flex items-center gap-1 rounded-sm px-2.5 py-1.5 text-xs font-medium text-text-muted hover:text-destructive hover:bg-destructive-soft/50 transition-colors cursor-pointer"
            title="Reset filters"
          >
            <ArrowCounterClockwise className="size-3" aria-hidden="true" />
            <span>Reset</span>
          </button>
        ) : null}
      </div>

      {/* ── Right: Filter & Sorter Controls ────────────────────────── */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Sorter Dropdown */}
        {setSortOption ? (
          <Dropdown
            id="storage-sort-select"
            aria-label="Sort documents"
            label="Sort:"
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
