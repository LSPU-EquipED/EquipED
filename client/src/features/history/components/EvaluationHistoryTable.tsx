import { useMemo, useState } from 'react';
import { Outlet, Link } from '@tanstack/react-router';
import {
  CaretLeft,
  CaretRight,
  ClipboardText,
  FileText,
  MagnifyingGlass,
  Spinner,
  Warning,
} from '@phosphor-icons/react';
import { useEvaluationHistory } from '../hooks/useEvaluationHistory';
import type { HistoryEvaluationItem } from '../types';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { BUTTON_STYLES, TABLE_STYLES, type StatusVariant } from '@/shared/constants/theme';
import { cn } from '@/shared/components/utils';

const STATUS_OPTIONS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'EVALUATING', label: 'Evaluating' },
  { value: 'SUBMITTED', label: 'Submitted' },
] as const;

function getStatusVariant(status: string): StatusVariant {
  const s = status.toUpperCase();
  if (s === 'FAILED' || s === 'ERROR') return 'destructive';
  if (s.startsWith('COMPLETED')) return 'success';
  if (s === 'EVALUATING' || s === 'PREPROCESSING' || s === 'SYNTHESIZING' || s === 'PROCESSING') return 'info';
  if (s === 'SUBMITTED' || s === 'PENDING' || s === 'QUEUED') return 'warning';
  return 'neutral';
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
}

export function EvaluationHistoryTable() {
  const [status, setStatus] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const { data, isLoading, isError } = useEvaluationHistory({
    status: status !== 'all' ? status : undefined,
    page,
    page_size: pageSize,
  });

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Client-side search filter over current page items if needed
  const filteredItems = useMemo(() => {
    const items = data?.items ?? [];
    if (!search.trim()) return items;
    const query = search.toLowerCase();
    return items.filter(
      (item) =>
        (item.document_title && item.document_title.toLowerCase().includes(query)) ||
        item.evaluation_id.toLowerCase().includes(query),
    );
  }, [data?.items, search]);

  const handleStatusChange = (val: string) => {
    setStatus(val);
    setPage(1);
  };

  return (
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-5">
      {/* Error alert */}
      {isError ? (
        <div className="flex items-center gap-2 rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs font-semibold text-destructive" role="alert">
          <Warning className="size-4 shrink-0" aria-hidden="true" />
          <span>Failed to load evaluation history.</span>
        </div>
      ) : null}

      {/* Unified Table Container */}
      <div className={TABLE_STYLES.wrapper}>
        {/* Table Filter & Search Toolbar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border bg-surface px-4 sm:px-6 py-3">
          <div className="flex items-center gap-2">
            <label
              htmlFor="history-status-filter"
              className="text-xs font-semibold uppercase tracking-wider text-text-muted whitespace-nowrap"
            >
              Status:
            </label>
            <select
              id="history-status-filter"
              value={status}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="h-8.5 rounded-sm border border-input bg-surface px-2.5 text-xs font-semibold text-text focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <div className="relative min-w-[12rem] sm:min-w-[16rem]">
              <MagnifyingGlass
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-text-muted"
                aria-hidden="true"
              />
              <input
                type="text"
                placeholder="Search by title or ID…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8.5 w-full rounded-sm border border-input bg-surface pl-8 pr-3 text-xs text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
                aria-label="Search evaluations"
              />
            </div>

            <span className="text-xs text-text-muted tabular-nums font-semibold whitespace-nowrap">
              {isLoading && !data
                ? 'Loading…'
                : `${total} evaluation${total === 1 ? '' : 's'} found`}
            </span>
          </div>
        </div>

        {/* Table Body */}
        <div className="overflow-x-auto">
          {isLoading && !data ? (
            <div className="flex justify-center items-center py-16 text-text-muted font-medium text-xs gap-2">
              <Spinner className="size-4 animate-spin text-primary" aria-hidden="true" />
              <span>Loading evaluation history…</span>
            </div>
          ) : !isError && (!data || data.items.length === 0) ? (
            <div className="px-6 py-16 text-center text-sm text-text-muted">
              <div className="flex flex-col items-center justify-center gap-2">
                <ClipboardText className="size-6 text-text-muted/60" aria-hidden="true" />
                <p className="font-semibold text-text">No evaluations yet</p>
                <p className="text-xs text-text-muted max-w-sm">
                  Evaluations will appear here once you run one from the Documents inventory.
                </p>
              </div>
            </div>
          ) : (
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[18rem]')}>
                    Document / SLM
                  </th>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Status
                  </th>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Submitted
                  </th>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Completed
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {filteredItems.map((record: HistoryEvaluationItem) => (
                  <tr key={record.evaluation_id} className={TABLE_STYLES.tr}>
                    <td className={TABLE_STYLES.td}>
                      <div className="flex flex-col">
                        <span className="font-semibold text-text line-clamp-1">
                          {record.document_title ?? '—'}
                        </span>
                        <span className="font-mono text-[10px] text-text-muted mt-0.5">
                          ID: {record.evaluation_id.slice(0, 18)}...
                        </span>
                      </div>
                    </td>
                    <td className={TABLE_STYLES.td}>
                      <Badge variant={getStatusVariant(record.status)} withDot>
                        {record.status.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className={cn(TABLE_STYLES.tdData, 'text-xs text-text-muted tabular-nums')}>
                      {formatDate(record.submitted_at)}
                    </td>
                    <td className={cn(TABLE_STYLES.tdData, 'text-xs text-text-muted tabular-nums')}>
                      {record.completed_at ? formatDate(record.completed_at) : '—'}
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'text-right')}>
                      <Link
                        to="/evaluations/$id"
                        params={{ id: record.evaluation_id }}
                        className={cn(
                          BUTTON_STYLES.base,
                          BUTTON_STYLES.variants.secondary,
                          BUTTON_STYLES.sizes.sm,
                          'text-xs h-7.5 px-3',
                        )}
                      >
                        <span>View Scorecard</span>
                        <CaretRight className="size-3" aria-hidden="true" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Compact Pagination Footer */}
        {!isLoading && total > 0 && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-border bg-surface-subtle px-4 sm:px-6 py-2.5 text-xs text-text-muted">
            <div className="flex items-center gap-3">
              <span className="tabular-nums font-medium">
                Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total} evaluations
              </span>
              <span className="text-border">|</span>
              <div className="flex items-center gap-1.5">
                <span>Show</span>
                <select
                  aria-label="Rows per page"
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1);
                  }}
                  className="h-7 rounded-sm border border-input bg-surface px-1.5 text-xs font-semibold text-text focus:outline-none focus:ring-1 focus:ring-ring"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
                <span>per page</span>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="h-7 px-2 text-xs"
                aria-label="Previous page"
              >
                <CaretLeft className="size-3" aria-hidden="true" />
                <span className="hidden sm:inline">Previous</span>
              </Button>
              <span className="px-2 font-medium tabular-nums text-text">
                {page} / {totalPages}
              </span>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="h-7 px-2 text-xs"
                aria-label="Next page"
              >
                <span className="hidden sm:inline">Next</span>
                <CaretRight className="size-3" aria-hidden="true" />
              </Button>
            </div>
          </div>
        )}
      </div>

      <Outlet />
    </section>
  );
}
