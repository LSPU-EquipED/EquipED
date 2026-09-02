import { Link } from '@tanstack/react-router';
import { ArrowRight, ArrowSquareOut, ClipboardText } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';
import { TableSkeleton } from '@/shared/components/TableSkeleton';
import { TABLE_STYLES, TYPOGRAPHY } from '@/shared/constants/theme';
import type { HomeEvaluationItem } from '../types';
import { formatDateOnly, getEvaluationStatusBadge } from '../utils/homeData';
interface RecentEvaluationsLedgerProps {
  evaluations: HomeEvaluationItem[];
  isLoading: boolean;
}

export function RecentEvaluationsLedger({
  evaluations,
  isLoading,
}: RecentEvaluationsLedgerProps) {
  return (
    <div className="rounded-md border border-border bg-surface overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-surface-subtle px-5 py-3.5">
        <div className="flex items-center gap-2">
          <ClipboardText className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text">
            Recent Evaluations
          </h2>
        </div>
        <Link
          to="/evaluations"
          className="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
        >
          <span>View All</span>
          <ArrowRight className="size-3 text-primary" aria-hidden="true" />
        </Link>
      </div>
      {/* Content */}
      <div className="flex-1">
        {isLoading ? (
          <TableSkeleton
            ariaLabel="Loading recent evaluations"
            columns={[
              { label: 'Document / Evaluation', skeletonClassName: 'h-5 w-full max-w-56' },
              { label: 'Status', skeletonClassName: 'h-5 w-20' },
              { label: 'Submitted', skeletonClassName: 'h-4 w-24' },
              { label: 'Action', skeletonClassName: 'h-8 w-16 ml-auto' },
            ]}
            rows={3}
          />
        ) : evaluations.length === 0 ? (
          <div className="p-8 text-center flex flex-col items-center justify-center">
            <ClipboardText className="size-8 text-text-muted/40 mb-2" aria-hidden="true" />
            <p className="text-sm font-semibold text-text">No evaluations yet</p>
            <p className="text-xs text-text-muted mt-1 max-w-xs">
              Evaluations will appear here after you evaluate an SLM.
            </p>
            <Link
              to="/documents"
              className="mt-4 inline-flex items-center gap-2 rounded-sm border border-border bg-surface px-3.5 py-2 text-xs font-semibold uppercase tracking-wider text-text hover:bg-surface-subtle transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span>Go to My SLMs</span>
              <ArrowRight className="size-3.5 text-text-muted" aria-hidden="true" />
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={TABLE_STYLES.th}>Document / Evaluation</th>
                  <th scope="col" className={TABLE_STYLES.th}>Status</th>
                  <th scope="col" className={TABLE_STYLES.th}>Submitted</th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>Action</th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {evaluations.map((ev) => {
                  const badge = getEvaluationStatusBadge(ev.status);

                  return (
                    <tr key={ev.evaluation_id} className={TABLE_STYLES.tr}>
                      <td className={cn(TABLE_STYLES.td, 'font-semibold max-w-[14rem]')}>
                        <div className="truncate" title={ev.document_title || ev.evaluation_id}>
                          {ev.document_title || 'Untitled SLM'}
                        </div>
                        <div className="text-[10px] font-mono text-text-muted truncate">
                          {ev.evaluation_id}
                        </div>
                      </td>
                      <td className={cn(TABLE_STYLES.td, 'whitespace-nowrap')}>
                        <span
                          className={cn(
                            'inline-flex rounded-xs px-2 py-0.5 text-xs font-semibold tracking-wide',
                            badge.className,
                          )}
                        >
                          {badge.label}
                        </span>
                      </td>
                      <td className={cn(TABLE_STYLES.tdData, 'text-text-muted whitespace-nowrap')}>
                        {formatDateOnly(ev.submitted_at)}
                      </td>
                      <td className={cn(TABLE_STYLES.td, 'text-right whitespace-nowrap')}>
                        <Link
                          to="/evaluations/$id"
                          params={{ id: ev.evaluation_id }}
                          className="inline-flex h-7 items-center gap-1 rounded-sm border border-border bg-surface px-2.5 text-[11px] font-semibold uppercase tracking-wider text-text hover:bg-surface-subtle transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <span>View</span>
                          <ArrowSquareOut className="size-3 text-text-muted" aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
