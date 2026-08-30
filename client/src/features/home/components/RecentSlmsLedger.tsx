import { Link } from '@tanstack/react-router';
import { ArrowRight, FileText, Loader2, PlayCircle } from 'lucide-react';
import type { ClientDocument } from '@/shared/types/documents';
import type { LatestEvaluationItem } from '@/shared/types/evaluations';
import { cn } from '@/shared/components/utils';
import { TABLE_STYLES, TYPOGRAPHY } from '@/shared/constants/theme';
import { getSlmDisplayStatus, type SlmStatusQueryState } from '@/shared/utils/slmDisplayStatus';
import { formatDateOnly } from '../utils/homeData';
interface RecentSlmsLedgerProps {
  documents: ClientDocument[];
  isLoading: boolean;
  latestEvalsByDocId?: Record<string, LatestEvaluationItem>;
  latestEvalsState?: SlmStatusQueryState;
}

export function RecentSlmsLedger({
  documents,
  isLoading,
  latestEvalsByDocId = {},
  latestEvalsState = {},
}: RecentSlmsLedgerProps) {
  return (
    <div className="rounded-md border border-border bg-surface overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-surface-subtle px-5 py-3.5">
        <div className="flex items-center gap-2">
          <FileText className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text">
            Recent SLMs
          </h2>
        </div>
        <Link
          to="/documents"
          className="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
        >
          <span>View All</span>
          <ArrowRight className="size-3 text-primary" aria-hidden="true" />
        </Link>
      </div>
      {/* Content */}
      <div className="flex-1">
        {isLoading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded-sm bg-surface-subtle" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="p-8 text-center flex flex-col items-center justify-center">
            <FileText className="size-8 text-text-muted/40 mb-2" aria-hidden="true" />
            <p className="text-sm font-semibold text-text">No SLMs uploaded yet</p>
            <p className="text-xs text-text-muted mt-1 max-w-xs">
              Use the Upload SLM action above to add course learning materials.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={TABLE_STYLES.th}>Title</th>
                  <th scope="col" className={TABLE_STYLES.th}>Program</th>
                  <th scope="col" className={TABLE_STYLES.th}>Status</th>
                  <th scope="col" className={TABLE_STYLES.th}>Uploaded</th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'text-right')}>Action</th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {documents.map((doc) => {
                  const latestEval = latestEvalsByDocId[doc.documentId];
                  const display = getSlmDisplayStatus(doc, latestEval, latestEvalsState);
                  const actionUrl = display.actionUrl;

                  return (
                    <tr key={doc.documentId} className={TABLE_STYLES.tr}>
                      <td className={cn(TABLE_STYLES.td, 'font-semibold max-w-[14rem]')}>
                        <div className="truncate" title={doc.title}>
                          {doc.title}
                        </div>
                        {doc.courseTitle && (
                          <div className="text-[11px] font-normal text-text-muted truncate">
                            {doc.courseTitle}
                          </div>
                        )}
                      </td>
                      <td className={cn(TABLE_STYLES.td, 'font-medium text-text-muted whitespace-nowrap')}>
                        {doc.program || '—'}
                      </td>
                      <td className={cn(TABLE_STYLES.td, 'whitespace-nowrap')}>
                        <span
                          className={cn(
                            'inline-flex items-center rounded-xs px-2 py-0.5 text-xs font-semibold tracking-wide',
                            display.badgeClass,
                          )}
                        >
                          {display.showSpinner ? (
                            <Loader2 className="mr-1 size-3 animate-spin" aria-hidden="true" />
                          ) : null}
                          {display.badgeLabel}
                        </span>
                      </td>
                      <td className={cn(TABLE_STYLES.tdData, 'text-text-muted whitespace-nowrap')}>
                        {formatDateOnly(doc.uploadedAt)}
                      </td>
                      <td className={cn(TABLE_STYLES.td, 'text-right whitespace-nowrap')}>
                        {display.isClickable && actionUrl ? (
                          <Link
                            to={actionUrl}
                            aria-label={display.ariaLabel}
                            className="inline-flex h-7 items-center gap-1 rounded-sm bg-primary px-2.5 text-[11px] font-semibold uppercase tracking-wider text-primary-foreground hover:bg-primary-strong transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            {display.actionType === 'start_evaluation' ? (
                              <PlayCircle className="size-3" aria-hidden="true" />
                            ) : null}
                            <span>{display.actionLabel}</span>
                          </Link>
                        ) : (
                          <span className="text-[11px] text-text-muted font-medium">
                            {display.actionLabel}
                          </span>
                        )}
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
