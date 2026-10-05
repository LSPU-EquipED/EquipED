import type { UseQueryResult } from '@tanstack/react-query';
import {
  ArrowCounterClockwise,
  FileText,
  MagnifyingGlass,
  Warning,
  X,
} from '@phosphor-icons/react';
import { Button, Dropdown, Skeleton, TABLE_STYLES, cn } from '@equiped/ui';
import { useValidationHistoryState } from '../hooks/useValidationHistoryState';
import type { ModelValidationItem, ModelValidationListResponse } from '../types';
import { ValidationReviewPanel } from './ValidationReviewPanel';
import { ValidationHistoryRow } from './ValidationHistoryRow';

const HISTORY_COLSPAN = 5;

const statusOptions = [
  { value: 'all', label: 'All statuses' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'EVALUATING', label: 'Evaluating' },
  { value: 'SYNTHESIZING', label: 'Synthesizing' },
  { value: 'FAILED', label: 'Failed' },
];

const modelOptions = [
  { value: 'all', label: 'All models' },
  { value: 'base', label: 'Base model' },
  { value: 'adapter', label: 'Adapter' },
];

const pageSizeOptions = [10, 20, 50].map((value) => ({
  value,
  label: `${value} per page`,
}));

const EMPTY_HISTORY_ITEMS: ModelValidationItem[] = [];

export function ValidationHistoryTable({
  history,
  onRerun,
}: {
  history: UseQueryResult<ModelValidationListResponse>;
  onRerun?: (item: ModelValidationItem) => void;
}) {
  const items = history.data?.items ?? EMPTY_HISTORY_ITEMS;
  const {
    expandedValidationId,
    setExpandedValidationId,
    pageSize,
    setPageSize,
    setPage,
    searchTerm,
    setSearchTerm,
    statusFilter,
    setStatusFilter,
    modelFilter,
    setModelFilter,
    hasActiveFilters,
    totalRecords,
    totalPages,
    currentPage,
    startRecord,
    endRecord,
    paginatedItems,
    selectedItem,
    resetFilters,
  } = useValidationHistoryState(items);

  return (
    <section
      className="w-full rounded-md border border-border bg-surface"
      aria-labelledby="validation-history-heading"
    >
      <div
        className={cn(
          selectedItem
            ? 'grid items-start lg:grid-cols-[minmax(0,1.08fr)_minmax(22rem,0.92fr)]'
            : 'block',
        )}
      >
        <div className="min-w-0">
          <div className="border-b border-border bg-surface px-5 py-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <FileText className="size-4 text-primary" aria-hidden="true" />
                  <h2 id="validation-history-heading" className="text-base font-semibold text-text">
                    Run history
                  </h2>
                  <span className="rounded-xs border border-border bg-surface-subtle px-1.5 py-0.5 text-[11px] font-mono font-semibold tabular-nums text-text-muted">
                    {items.length}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-text-muted">
                  Open a run to review its expected scores, model scores, and bound rubric
                  revisions.
                </p>
              </div>

              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <label className="relative block min-w-0 sm:w-56">
                  <MagnifyingGlass
                    className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
                    aria-hidden="true"
                  />
                  <input
                    value={searchTerm}
                    onChange={(event) => {
                      setSearchTerm(event.target.value);
                    }}
                    placeholder="Search runs"
                    aria-label="Search validation runs"
                    className="h-10 w-full rounded-sm border border-input bg-surface pl-9 pr-8 text-sm text-text placeholder:text-text-muted focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  {searchTerm ? (
                    <button
                      type="button"
                      aria-label="Clear run search"
                      onClick={() => {
                        setSearchTerm('');
                      }}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-xs p-1 text-text-muted hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <X className="size-3.5" aria-hidden="true" />
                    </button>
                  ) : null}
                </label>
                <Dropdown
                  value={statusFilter}
                  onChange={setStatusFilter}
                  options={statusOptions}
                  aria-label="Filter validation runs by status"
                  size="md"
                  className="min-w-36"
                />
                <Dropdown
                  value={modelFilter}
                  onChange={setModelFilter}
                  options={modelOptions}
                  aria-label="Filter validation runs by model"
                  size="md"
                  className="min-w-32"
                />
                {hasActiveFilters ? (
                  <button
                    type="button"
                    onClick={resetFilters}
                    className="inline-flex h-10 items-center justify-center gap-1.5 rounded-sm border border-border bg-surface px-3 text-xs font-semibold text-text-muted transition-colors hover:border-destructive/30 hover:bg-destructive-soft/50 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <ArrowCounterClockwise className="size-3.5" aria-hidden="true" />
                    Reset
                  </button>
                ) : null}
              </div>
            </div>
          </div>

          <div
            className="overflow-hidden"
            role={history.isLoading ? 'status' : undefined}
            aria-label={history.isLoading ? 'Loading validation history' : undefined}
            aria-busy={history.isLoading}
          >
            <table className={cn(TABLE_STYLES.table, 'w-full table-fixed')}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th className={cn(TABLE_STYLES.th, 'w-[42%]')}>Run</th>
                  <th className={cn(TABLE_STYLES.th, 'w-[16%]')}>Status</th>
                  <th className={cn(TABLE_STYLES.th, 'w-[16%] text-right')}>Agreement</th>
                  <th className={cn(TABLE_STYLES.th, 'w-[14%] text-right')}>Error / runtime</th>
                  <th className={cn(TABLE_STYLES.th, 'w-[12%] text-right')}>Action</th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {history.isLoading
                  ? Array.from({ length: 5 }).map((_, rowIndex) => (
                      <tr key={rowIndex}>
                        {Array.from({ length: HISTORY_COLSPAN }).map((__, columnIndex) => (
                          <td key={columnIndex} className={TABLE_STYLES.td}>
                            <Skeleton
                              className={cn(
                                columnIndex === 0 ? 'h-5 w-full max-w-64' : 'h-4 w-20',
                                columnIndex === HISTORY_COLSPAN - 1 && 'ml-auto',
                              )}
                            />
                          </td>
                        ))}
                      </tr>
                    ))
                  : null}
                {history.isError ? (
                  <tr>
                    <td
                      colSpan={HISTORY_COLSPAN}
                      className="bg-destructive-soft px-4 py-10 text-center text-xs font-semibold text-destructive"
                    >
                      <div className="flex items-center justify-center gap-2">
                        <Warning className="size-4" aria-hidden="true" />
                        Unable to load validation history.
                      </div>
                    </td>
                  </tr>
                ) : null}
                {!history.isLoading && !history.isError
                  ? paginatedItems.map((item) => {
                      const compared = item.criterion_scores.filter(
                        (score) => score.actual_score != null,
                      );
                      const exactMatches = compared.filter(
                        (score) => score.actual_score === score.expected_score,
                      ).length;
                      const isExpanded = expandedValidationId === item.validation_id;
                      return (
                        <ValidationHistoryRow
                          key={item.validation_id}
                          item={item}
                          isExpanded={isExpanded}
                          comparedCount={compared.length}
                          exactMatches={exactMatches}
                          onToggle={() => setExpandedValidationId(item.validation_id)}
                          onRerun={onRerun}
                        />
                      );
                    })
                  : null}
                {!history.isLoading && !history.isError && totalRecords === 0 ? (
                  <tr>
                    <td
                      colSpan={HISTORY_COLSPAN}
                      className="px-4 py-14 text-center text-text-muted"
                    >
                      <FileText className="mx-auto size-8 text-text-muted/40" aria-hidden="true" />
                      <p className="mt-2 text-sm font-semibold text-text">
                        {hasActiveFilters
                          ? 'No matching validation runs'
                          : 'No validation runs yet'}
                      </p>
                      <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed">
                        {hasActiveFilters
                          ? 'Try clearing one of the filters to see more runs.'
                          : 'Submit a benchmark evaluation in the New Benchmark Run workspace to record accuracy results.'}
                      </p>
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>

          {!history.isLoading && !history.isError && totalRecords > 0 ? (
            <div className="flex flex-col gap-3 border-t border-border bg-surface px-5 py-3 text-xs text-text-muted sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-3">
                <span>
                  Showing{' '}
                  <strong className="font-semibold tabular-nums text-text">
                    {startRecord}–{endRecord}
                  </strong>{' '}
                  of{' '}
                  <strong className="font-semibold tabular-nums text-text">{totalRecords}</strong>
                </span>
                <Dropdown
                  value={pageSize}
                  onChange={setPageSize}
                  options={pageSizeOptions}
                  aria-label="Runs per page"
                  placement="top"
                  size="sm"
                  className="min-w-28"
                />
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage(Math.max(1, currentPage - 1))}
                  disabled={currentPage <= 1}
                >
                  Previous
                </Button>
                <span className="px-1 font-medium text-text">
                  Page <strong className="font-bold tabular-nums">{currentPage}</strong> of{' '}
                  <strong className="font-bold tabular-nums">{totalPages}</strong>
                </span>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage(Math.min(totalPages, currentPage + 1))}
                  disabled={currentPage >= totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </div>

        {selectedItem ? (
          <ValidationReviewPanel
            item={selectedItem}
            onClose={() => setExpandedValidationId(null)}
          />
        ) : null}
      </div>
    </section>
  );
}
