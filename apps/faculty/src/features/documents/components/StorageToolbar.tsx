import { MagnifyingGlass, Plus, UploadSimple } from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import type { StorageProgramFilter, StorageStatusFilter } from '../hooks/useSlmStorage';

interface StorageToolbarProps {
  programFilter: StorageProgramFilter;
  setProgramFilter: (val: StorageProgramFilter) => void;
  statusFilter: StorageStatusFilter;
  setStatusFilter: (val: StorageStatusFilter) => void;
  search: string;
  setSearch: (val: string) => void;
  totalModules: number;
  onOpenUpload: () => void;
}

const PROGRAM_TABS: { id: StorageProgramFilter; label: string }[] = [
  { id: 'ALL', label: 'All Modules' },
  { id: 'BSCS', label: 'BSCS (Comp Sci)' },
  { id: 'BSInfoTech', label: 'BSInfoTech (IT)' },
];

export function StorageToolbar({
  programFilter,
  setProgramFilter,
  statusFilter,
  setStatusFilter,
  search,
  setSearch,
  totalModules,
  onOpenUpload,
}: StorageToolbarProps) {
  return (
    <div className="rounded-md border border-border bg-surface overflow-hidden shadow-none space-y-0">
      {/* ── Top Bar: Program Filter Tabs & Action Button ───────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border bg-surface-subtle px-4 sm:px-6 py-2.5">
        <div
          role="tablist"
          aria-label="Filter modules by academic program"
          className="flex flex-wrap items-center gap-1"
        >
          {PROGRAM_TABS.map((tab) => {
            const isActive = programFilter === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => setProgramFilter(tab.id)}
                className={cn(
                  'rounded-xs px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer select-none',
                  isActive
                    ? 'bg-primary text-primary-foreground font-bold shadow-xs'
                    : 'text-text-muted hover:text-text hover:bg-surface',
                )}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <Button
          type="button"
          variant="primary"
          size="sm"
          onClick={onOpenUpload}
          className="h-8.5 px-3.5 text-xs font-bold uppercase tracking-wider gap-1.5 shrink-0 self-start sm:self-auto"
        >
          <Plus className="size-3.5" aria-hidden="true" />
          <span>Upload SLM</span>
        </Button>
      </div>

      {/* ── Bottom Bar: Status Filter & Search Input ───────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 sm:px-6 py-2.5 bg-surface">
        <div className="flex items-center gap-2">
          <label
            htmlFor="storage-status-filter"
            className="text-xs font-semibold uppercase tracking-wider text-text-muted whitespace-nowrap"
          >
            Status:
          </label>
          <select
            id="storage-status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StorageStatusFilter)}
            className="h-8 rounded-sm border border-input bg-surface px-2.5 text-xs font-semibold text-text focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
          >
            <option value="all">All Statuses</option>
            <option value="PROCESSED">Ready for Review</option>
            <option value="PROCESSING">Parsing & Ingestion</option>
            <option value="FAILED">Processing Failed</option>
          </select>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="relative min-w-[14rem] sm:min-w-[18rem]">
            <MagnifyingGlass
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-text-muted"
              aria-hidden="true"
            />
            <input
              type="text"
              placeholder="Search module, CS101, title…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 w-full rounded-sm border border-input bg-surface pl-8 pr-3 text-xs text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="Search course modules"
            />
          </div>

          <span className="text-xs text-text-muted tabular-nums font-semibold whitespace-nowrap">
            {totalModules} module{totalModules === 1 ? '' : 's'}
          </span>
        </div>
      </div>
    </div>
  );
}
