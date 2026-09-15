import { useMemo, useState } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import { ClockCounterClockwise, FileText, Warning } from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';
import { Skeleton } from '@/shared/components/Skeleton';
import { TABLE_STYLES } from '@/shared/constants/theme';
import { cn } from '@/shared/components/utils';
import type { ModelValidationListResponse } from '../types';
import { HISTORY_COLSPAN } from '../utils/helpers';
import { HistoryRow } from './ValidationDetail';

export function ValidationHistoryTable({
  history,
}: {
  history: UseQueryResult<ModelValidationListResponse>;
}) {
  const [expandedValidationId, setExpandedValidationId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const items = history.data?.items ?? [];
  const totalRecords = items.length;
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const startRecord = totalRecords > 0 ? (page - 1) * pageSize + 1 : 0;
  const endRecord = Math.min(page * pageSize, totalRecords);

  const paginatedItems = useMemo(
    () => items.slice((page - 1) * pageSize, page * pageSize),
    [items, page, pageSize],
  );

  return (
    <div className={TABLE_STYLES.wrapper}>
      {/* Table Header Strip */}
      <div className="flex items-center justify-between border-b border-border bg-surface-subtle px-5 py-3.5">
        <div className="flex items-center gap-2">
          <ClockCounterClockwise className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-text">
            Validation History
          </h2>
        </div>
        <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider">
          {totalRecords} Recorded Runs
        </span>
      </div>

      {/* 7-Column Table Without Horizontal Scrolling */}
      <div
        className="overflow-x-auto"
        role={history.isLoading ? 'status' : undefined}
        aria-label={history.isLoading ? 'Loading validation history' : undefined}
        aria-busy={history.isLoading}
      >
        <table className={TABLE_STYLES.table}>
          <thead className={TABLE_STYLES.thead}>
            <tr>
              <th className={cn(TABLE_STYLES.th, 'w-auto min-w-[14rem]')}>SLM Document</th>
              <th className={cn(TABLE_STYLES.th, 'w-28')}>Status</th>
              <th className={cn(TABLE_STYLES.th, 'w-36 text-right')}>Accuracy (Exact)</th>
              <th className={cn(TABLE_STYLES.th, 'w-28 text-right')}>Mean Error</th>
              <th className={cn(TABLE_STYLES.th, 'w-28 text-right')}>Latency</th>
              <th className={cn(TABLE_STYLES.th, 'w-28 text-right')}>Toxicity</th>
              <th className={cn(TABLE_STYLES.th, 'w-36 text-right')}>Action</th>
            </tr>
          </thead>
          <tbody className={TABLE_STYLES.tbody}>
            {history.isLoading
              ? Array.from({ length: 5 }).map((_, rowIndex) => (
                  <tr key={rowIndex}>
                    {Array.from({ length: 7 }).map((__, columnIndex) => (
                      <td key={columnIndex} className={TABLE_STYLES.td}>
                        <Skeleton
                          className={cn(
                            columnIndex === 0 ? 'h-5 w-full max-w-64' : 'h-4 w-20',
                            columnIndex === 6 && 'ml-auto',
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
                  className="px-4 py-10 text-center font-semibold text-destructive text-xs bg-destructive-soft"
                >
                  <div className="flex items-center justify-center gap-2">
                    <Warning className="size-4 text-destructive" aria-hidden="true" />
                    <span>Unable to load validation history.</span>
                  </div>
                </td>
              </tr>
            ) : null}
            {paginatedItems.map((item) => {
              const compared = item.criterion_scores.filter(
                (score) => score.actual_score != null,
              );
              const exactMatches = compared.filter(
                (score) => score.actual_score === score.expected_score,
              ).length;
              const isExpanded = expandedValidationId === item.validation_id;
              return (
                <HistoryRow
                  key={item.validation_id}
                  item={item}
                  isExpanded={isExpanded}
                  isAnyExpanded={expandedValidationId !== null}
                  comparedCount={compared.length}
                  exactMatches={exactMatches}
                  onToggle={() =>
                    setExpandedValidationId((current) =>
                      current === item.validation_id ? null : item.validation_id,
                    )
                  }
                  onClose={() => setExpandedValidationId(null)}
                />
              );
            })}
            {!history.isLoading && !history.isError && totalRecords === 0 ? (
              <tr>
                <td
                  colSpan={HISTORY_COLSPAN}
                  className="px-4 py-12 text-center text-text-muted text-xs space-y-1.5"
                >
                  <FileText className="size-8 text-text-muted/40 mx-auto" aria-hidden="true" />
                  <p className="font-semibold text-text">No validation runs yet.</p>
                  <p className="text-[11px] text-text-muted">
                    Submit a benchmark evaluation in the New Benchmark Run tab to record accuracy results.
                  </p>
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {/* ── Pagination & Record Navigation Footer ─────────────────────── */}
      {!history.isLoading && !history.isError && totalRecords > 0 ? (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-border bg-surface px-5 py-3 text-xs text-text-muted">
          <div className="flex flex-wrap items-center gap-4">
            <span>
              Showing{' '}
              <strong className="font-semibold text-text tabular-nums">
                {startRecord}–{endRecord}
              </strong>{' '}
              of <strong className="font-semibold text-text tabular-nums">{totalRecords}</strong> records
            </span>

            <div className="flex items-center gap-1.5 pl-3 border-l border-border">
              <span className="text-[11px] text-text-muted font-medium">Per page:</span>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setPage(1);
                }}
                aria-label="Records per page"
                className="h-7 border border-input bg-surface px-2 rounded-xs text-xs font-semibold text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring cursor-pointer"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="h-7 px-2.5 text-xs font-semibold"
            >
              Previous
            </Button>
            <span className="px-2 text-xs font-medium text-text">
              Page <strong className="font-bold tabular-nums">{page}</strong> of{' '}
              <strong className="font-bold tabular-nums">{totalPages}</strong>
            </span>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="h-7 px-2.5 text-xs font-semibold"
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
