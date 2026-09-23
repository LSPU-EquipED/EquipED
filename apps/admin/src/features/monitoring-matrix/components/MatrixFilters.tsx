import { useRef } from 'react';
import { ArrowCounterClockwise, MagnifyingGlass, X } from '@phosphor-icons/react';
import { Dropdown } from '@equiped/ui';

interface MatrixFiltersProps {
  searchQuery?: string;
  onSearchChange?: (val: string) => void;
  program: string;
  status: string;
  onProgramChange: (val: string) => void;
  onStatusChange: (val: string) => void;
  onResetFilters?: () => void;
}

export function MatrixFilters({
  searchQuery = '',
  onSearchChange,
  program,
  status,
  onProgramChange,
  onStatusChange,
  onResetFilters,
}: MatrixFiltersProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const hasActiveFilters = program !== 'all' || status !== 'all' || searchQuery.trim().length > 0;

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      {/* ── Left: Search input ────────────────────────────────────────── */}
      <div className="relative w-full sm:w-72 md:w-80">
        <MagnifyingGlass
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
          aria-hidden="true"
        />
        <input
          ref={inputRef}
          type="text"
          maxLength={100}
          placeholder="Search by module title, faculty, or program…"
          value={searchQuery}
          onChange={(e) => onSearchChange?.(e.target.value)}
          className="h-10 w-full rounded-sm border border-input bg-surface pl-9 pr-8 text-xs sm:text-sm text-text placeholder:text-text-muted focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring"
          aria-label="Search monitoring matrix"
        />
        {searchQuery ? (
          <button
            type="button"
            onClick={() => {
              inputRef.current?.focus();
              onSearchChange?.('');
            }}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text cursor-pointer p-0.5"
            aria-label="Clear search"
          >
            <X className="size-3.5" aria-hidden="true" />
          </button>
        ) : null}
      </div>

      {/* ── Right: Filter Dropdowns & Reset Action ────────────────────── */}
      <div className="flex flex-wrap items-center gap-2.5 sm:ml-auto">
        <div className="w-44 sm:w-52">
          <Dropdown
            value={program}
            onChange={onProgramChange}
            aria-label="Filter by program"
            size="md"
            className="w-full"
            options={[
              { value: 'all', label: 'All Programs' },
              { value: 'BSCS', label: 'Computer Science' },
              { value: 'BSInfoTech', label: 'Information Technology' },
            ]}
          />
        </div>

        <div className="w-40 sm:w-48">
          <Dropdown
            value={status}
            onChange={onStatusChange}
            aria-label="Filter by status"
            size="md"
            className="w-full"
            options={[
              { value: 'all', label: 'All Statuses' },
              { value: 'IN_PROGRESS', label: 'In Progress' },
              { value: 'COMPLETED', label: 'Completed' },
              { value: 'FAILED', label: 'Failed' },
              { value: 'EVALUATING', label: 'Evaluating' },
            ]}
          />
        </div>

        {hasActiveFilters && onResetFilters && (
          <button
            type="button"
            onClick={() => {
              inputRef.current?.focus();
              onResetFilters();
            }}
            className="inline-flex h-10 items-center gap-1.5 rounded-sm border border-border bg-surface px-3 text-xs font-medium text-text-muted transition-colors hover:bg-destructive-soft/50 hover:text-destructive hover:border-destructive/30 cursor-pointer"
            title="Reset filters"
          >
            <ArrowCounterClockwise className="size-3.5" aria-hidden="true" />
            <span>Reset</span>
          </button>
        )}
      </div>
    </div>
  );
}
