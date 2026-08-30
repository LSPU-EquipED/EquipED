import { useState } from 'react';
import { Outlet, Link } from '@tanstack/react-router';
import { ArrowSquareOut, Spinner, Warning } from '@phosphor-icons/react';
import { useEvaluationHistory } from '../hooks/useEvaluationHistory';
import type { HistoryEvaluationItem } from '../types';
import { Badge } from '@/shared/components/Badge';
import { CARD_STYLES, TABLE_STYLES, type StatusVariant } from '@/shared/constants/theme';
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
    month: '2-digit',
    day: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

export function EvaluationHistoryTable() {
  const [status, setStatus] = useState('all');

  const { data, isLoading, isError } = useEvaluationHistory({
    status: status !== 'all' ? status : undefined,
  });

  return (
    <section className="mx-auto grid w-full max-w-[108rem] gap-7">
      {/* Status filter bar */}
      <div className="flex flex-wrap items-center justify-end gap-4">
        <div className="flex items-center gap-3">
          <label
            htmlFor="history-status-filter"
            className="text-xs font-semibold uppercase tracking-wider text-text-muted whitespace-nowrap"
          >
            Filter by status
          </label>
          <select
            id="history-status-filter"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-10 border border-input bg-surface px-3 focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent rounded-sm text-sm font-semibold text-text cursor-pointer min-w-[10rem] transition-colors"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table card */}
      <div className={CARD_STYLES.ledger}>
        {/* Table meta bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-6 py-4 bg-surface-subtle">
          <p className="text-sm font-medium text-text">
            {isLoading && !data
              ? 'Loading records…'
              : `${data?.total ?? 0} evaluation${(data?.total ?? 0) === 1 ? '' : 's'} found`}
          </p>
          <p className="text-xs text-text-muted font-semibold uppercase tracking-wider">
            Human review is authoritative.
          </p>
        </div>

        <div className="p-6">
          {/* Error state */}
          {isError ? (
            <div className="flex items-center gap-2 rounded-sm border border-destructive/20 bg-destructive-soft px-4 py-3 text-sm text-destructive font-semibold">
              <Warning className="size-4 shrink-0" aria-hidden="true" />
              Failed to load evaluation history.
            </div>
          ) : null}

          {/* Loading state */}
          {isLoading && !data ? (
            <div className="flex justify-center items-center py-12 text-text-muted font-medium text-sm gap-2">
              <Spinner className="size-5 animate-spin text-primary" aria-hidden="true" />
              <span>Loading evaluation history…</span>
            </div>
          ) : null}

          {/* Empty state */}
          {!isError && !isLoading && (!data || data.items.length === 0) ? (
            <div className="grid gap-2 rounded-sm border border-dashed border-border bg-surface-subtle/50 px-6 py-12 text-center">
              <h3 className="text-lg font-semibold text-text">No evaluations yet</h3>
              <p className="text-sm text-text-muted">
                Evaluations will appear here once you run one from the Documents inventory.
              </p>
            </div>
          ) : null}

          {/* Table */}
          {!isError && data && data.items.length > 0 ? (
            <div className="overflow-x-auto rounded-sm border border-border">
              <table className={TABLE_STYLES.table}>
                <thead className={TABLE_STYLES.thead}>
                  <tr>
                    <th className={cn(TABLE_STYLES.th, 'min-w-[20rem]')}>
                      Document / SLM
                    </th>
                    <th className={TABLE_STYLES.th}>Status</th>
                    <th className={TABLE_STYLES.th}>Submitted</th>
                    <th className={TABLE_STYLES.th}>Completed</th>
                    <th className={cn(TABLE_STYLES.th, 'text-right')}>Action</th>
                  </tr>
                </thead>
                <tbody className={TABLE_STYLES.tbody}>
                  {data.items.map((record: HistoryEvaluationItem) => (
                    <tr key={record.evaluation_id} className={TABLE_STYLES.tr}>
                      <td className={TABLE_STYLES.td}>
                        <div className="flex flex-col gap-0.5">
                          <span className="truncate max-w-[22rem] font-semibold text-text">
                            {record.document_title ?? '—'}
                          </span>
                          <span className="text-[10px] tabular-nums font-bold text-text-muted uppercase tracking-wider">
                            {record.evaluation_id}
                          </span>
                        </div>
                      </td>
                      <td className={TABLE_STYLES.td}>
                        <Badge variant={getStatusVariant(record.status)}>
                          {record.status.replace('_', ' ')}
                        </Badge>
                      </td>
                      <td className={cn(TABLE_STYLES.tdData, 'text-text-muted font-medium')}>
                        {formatDate(record.submitted_at)}
                      </td>
                      <td className={cn(TABLE_STYLES.tdData, 'text-text-muted font-medium')}>
                        {record.completed_at ? formatDate(record.completed_at) : '—'}
                      </td>
                      <td className={cn(TABLE_STYLES.td, 'text-right')}>
                        <Link
                          to="/evaluations/$id"
                          params={{ id: record.evaluation_id }}
                          className="inline-flex h-8 items-center justify-center border border-border bg-surface hover:bg-surface-subtle text-text px-3 rounded-sm text-xs font-semibold uppercase tracking-wider transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                        >
                          <span>View</span>
                          <ArrowSquareOut className="size-3 ml-1.5" aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>

      <Outlet />
    </section>
  );
}
