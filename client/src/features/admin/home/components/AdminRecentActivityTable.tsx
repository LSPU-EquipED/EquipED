import { Link } from '@tanstack/react-router';
import {
  CaretRight,
  ClipboardText,
  Warning,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { BUTTON_STYLES, TABLE_STYLES, type StatusVariant } from '@/shared/constants/theme';
import { cn } from '@/shared/components/utils';
import type { MonitoringMatrixRow } from '../types';

function getStatusVariant(status: string): StatusVariant {
  const s = status.toUpperCase();
  if (s === 'FAILED' || s === 'ERROR') return 'destructive';
  if (s === 'COMPLETED') return 'success';
  if (s === 'COMPLETED_PARTIAL') return 'warning';
  if (s === 'EVALUATING' || s === 'PREPROCESSING' || s === 'SYNTHESIZING' || s === 'PROCESSING') return 'info';
  if (s === 'SUBMITTED' || s === 'QUEUED' || s === 'PENDING') return 'warning';
  return 'neutral';
}

const DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
});

interface AdminRecentActivityTableProps {
  recentActivity: MonitoringMatrixRow[];
  isLoading: boolean;
  isError: boolean;
}

export function AdminRecentActivityTable({
  recentActivity,
  isLoading,
  isError,
}: AdminRecentActivityTableProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-bold text-text tracking-tight">
            Latest Institutional Evaluations
          </h2>
          <p className="text-xs text-text-muted mt-0.5">
            Recent multi-agent scoring outcomes from the monitoring matrix.
          </p>
        </div>
        <Link
          to="/matrix"
          className={cn(
            BUTTON_STYLES.base,
            BUTTON_STYLES.variants.secondary,
            BUTTON_STYLES.sizes.sm,
            'text-xs font-semibold self-start sm:self-auto h-8 px-3',
          )}
        >
          <span>View Full Matrix</span>
          <CaretRight className="size-3.5 text-text-muted" aria-hidden="true" />
        </Link>
      </div>

      <div className={TABLE_STYLES.wrapper}>
        {isLoading ? (
          <div className="space-y-3 p-6">
            <div className="animate-pulse bg-surface-subtle h-9 w-full rounded-sm" />
            <div className="animate-pulse bg-surface-subtle h-9 w-full rounded-sm" />
            <div className="animate-pulse bg-surface-subtle h-9 w-full rounded-sm" />
          </div>
        ) : isError ? (
          <div className="py-16 text-center space-y-2">
            <Warning className="size-6 text-destructive mx-auto" aria-hidden="true" />
            <p className="text-xs font-semibold text-destructive">
              Unable to load recent activity from the monitoring matrix.
            </p>
            <p className="text-[11px] text-text-muted">
              Please verify database connectivity and try refreshing.
            </p>
          </div>
        ) : recentActivity.length === 0 ? (
          <div className="py-16 text-center space-y-2">
            <ClipboardText className="size-6 text-text-muted/60 mx-auto" aria-hidden="true" />
            <p className="text-xs font-semibold text-text">No evaluation activity yet</p>
            <p className="text-[11px] text-text-muted max-w-sm mx-auto">
              Evaluations executed by faculty will populate this operational feed.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[18rem]')}>
                    SLM Document / Module
                  </th>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Program
                  </th>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Status
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
                    Synthesized Score
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
                    Flags
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>
                    Updated
                  </th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {recentActivity.map((row: MonitoringMatrixRow) => (
                  <tr key={row.matrix_id || row.document_id} className={TABLE_STYLES.tr}>
                    <td className={TABLE_STYLES.td}>
                      <div className="flex flex-col">
                        <span className="font-semibold text-text line-clamp-1">
                          {row.document_title || 'Untitled SLM'}
                        </span>
                        {row.faculty_name ? (
                          <span className="text-[11px] text-text-muted mt-0.5">
                            Faculty: {row.faculty_name}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'text-xs text-text-muted font-medium')}>
                      {row.program || '—'}
                    </td>
                    <td className={TABLE_STYLES.td}>
                      <Badge variant={getStatusVariant(row.evaluation_status)} withDot>
                        {row.evaluation_status.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className={cn(TABLE_STYLES.tdData, 'text-right font-semibold text-text tabular-nums')}>
                      {row.synthesized_score != null ? (
                        <span>
                          {row.synthesized_score.toFixed(2)}
                          <span className="text-text-muted font-normal text-[11px]"> / 4.00</span>
                        </span>
                      ) : (
                        <span className="text-text-muted font-normal">—</span>
                      )}
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'text-right')}>
                      {row.flag_count > 0 ? (
                        <span className="inline-flex items-center justify-center min-w-5 h-5 rounded-full bg-accent-soft text-accent-foreground text-[11px] font-bold px-1.5 border border-accent/30 tabular-nums">
                          {row.flag_count}
                        </span>
                      ) : (
                        <span className="text-text-muted text-xs">—</span>
                      )}
                    </td>
                    <td className={cn(TABLE_STYLES.tdData, 'text-right text-xs text-text-muted tabular-nums')}>
                      {DATE_FORMATTER.format(new Date(row.last_updated))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
