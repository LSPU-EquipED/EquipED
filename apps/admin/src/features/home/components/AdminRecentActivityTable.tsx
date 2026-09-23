import { Link } from '@tanstack/react-router';
import {
  CaretRight,
  ClipboardText,
  Warning,
} from '@phosphor-icons/react';
import {
  Badge,
  TABLE_STYLES,
  TableSkeleton,
  cn,
  getEvaluationStatusVariant,
} from '@equiped/ui';
import type { MonitoringMatrixRow } from '../types';

const DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
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
    <section aria-labelledby="admin-activity-heading" className="min-w-0 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="admin-activity-heading" className="text-base font-semibold text-text">Recent evaluations</h2>
          <p className="mt-1 text-xs text-text-muted">Latest module records across academic programs.</p>
        </div>
        <Link to="/matrix" className="inline-flex min-h-10 items-center gap-1 text-xs font-semibold text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring">
          View full matrix <CaretRight className="size-3.5" aria-hidden="true" />
        </Link>
      </div>

      <div className={TABLE_STYLES.wrapper}>
        {isLoading ? (
          <TableSkeleton
            ariaLabel="Loading recent evaluation activity"
            columns={[
              { label: 'Module', headerClassName: 'min-w-[14rem]', skeletonClassName: 'h-4 w-52' },
              { label: 'Status', skeletonClassName: 'h-5 w-24' },
              { label: 'Score / 4', headerClassName: 'text-right whitespace-nowrap', skeletonClassName: 'h-4 w-16 ml-auto' },
              { label: 'Flags', headerClassName: 'text-right', skeletonClassName: 'h-5 w-8 ml-auto' },
              { label: 'Updated', headerClassName: 'text-right whitespace-nowrap', skeletonClassName: 'h-4 w-24 ml-auto' },
              { label: '', headerClassName: 'w-10', skeletonClassName: 'h-4 w-4 ml-auto' },
            ]}
          />
        ) : isError ? (
          <div className="px-4 py-16 text-center space-y-2">
            <Warning className="size-6 text-destructive mx-auto" aria-hidden="true" />
            <p className="text-xs font-semibold text-destructive">
              Unable to load recent activity from the monitoring matrix.
            </p>
            <p className="text-[11px] text-text-muted">
              Refresh this page to try again, or open the monitoring matrix.
            </p>
          </div>
        ) : recentActivity.length === 0 ? (
          <div className="px-4 py-16 text-center space-y-2">
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
                  <th scope="col" className={cn(TABLE_STYLES.th, 'min-w-[14rem] text-xs font-semibold normal-case tracking-normal')}>
                    Module
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-xs font-semibold normal-case tracking-normal')}>
                    Status
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right whitespace-nowrap text-xs font-semibold normal-case tracking-normal')}>
                    Score / 4
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right text-xs font-semibold normal-case tracking-normal')}>
                    Flags
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right whitespace-nowrap text-xs font-semibold normal-case tracking-normal')}>
                    Updated
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-10 text-center')}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {recentActivity.map((row: MonitoringMatrixRow) => (
                  <tr key={row.matrix_id || row.document_id} className={TABLE_STYLES.tr}>
                    <td className={TABLE_STYLES.td}>
                      <div className="flex flex-col min-w-0">
                        <Link
                          to="/matrix/$documentId"
                          params={{ documentId: row.document_id }}
                          className="font-semibold text-sm text-text hover:text-primary transition-colors block max-w-sm break-words focus-visible:outline-2 focus-visible:outline-ring"
                        >
                          {row.document_title || 'Untitled SLM'}
                        </Link>
                        <div className="flex items-center gap-2 text-xs text-text-muted mt-1 flex-wrap">
                          {row.program ? (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded-xs text-[10px] font-medium uppercase tracking-wide bg-surface-subtle/80 text-text-muted border border-border/70">
                              {row.program}
                            </span>
                          ) : null}
                          {row.faculty_name ? (
                            <span className="text-xs text-text-muted">
                              Faculty: {row.faculty_name}
                            </span>
                          ) : null}
                        </div>
                      </div>
                    </td>
                    <td className={TABLE_STYLES.td}>
                      <Badge variant={getEvaluationStatusVariant(row.evaluation_status)} withDot>
                        {row.evaluation_status.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className={cn(TABLE_STYLES.tdData, 'text-right whitespace-nowrap')}>
                      {row.synthesized_score != null ? (
                        <div className="inline-flex items-baseline gap-1">
                          <span className="font-bold text-sm text-text tabular-nums">
                            {row.synthesized_score.toFixed(2)}
                          </span>
                          <span className="text-text-muted font-normal text-xs"> / 4.00</span>
                        </div>
                      ) : (
                        <span className="text-text-muted font-normal text-xs">—</span>
                      )}
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'text-right')}>
                      {row.flag_count > 0 ? (
                        <span className="inline-flex items-center justify-center min-w-5 h-5 rounded-full bg-warning-soft text-warning text-[11px] font-bold px-1.5 border border-warning/25 tabular-nums">
                          {row.flag_count}
                        </span>
                      ) : (
                        <span className="text-text-muted text-xs">—</span>
                      )}
                    </td>
                    <td
                      className={cn(TABLE_STYLES.tdData, 'text-right text-xs font-medium text-text-muted tabular-nums whitespace-nowrap')}
                      title={new Date(row.last_updated).toLocaleString()}
                    >
                      {DATE_FORMATTER.format(new Date(row.last_updated))}
                    </td>
                    <td className={cn(TABLE_STYLES.td, 'w-10 text-center')}>
                      <Link
                        to="/matrix/$documentId"
                        params={{ documentId: row.document_id }}
                        className="inline-flex size-7 items-center justify-center rounded-xs text-text-muted hover:bg-surface-subtle hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary transition-colors"
                        title={`View synthesis for ${row.document_title || 'module'}`}
                        aria-label={`View synthesis for ${row.document_title || 'module'}`}
                      >
                        <CaretRight className="size-4" aria-hidden="true" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
