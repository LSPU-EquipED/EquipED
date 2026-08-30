import { CaretRight, Spinner } from '@phosphor-icons/react';
import { Link, useNavigate } from '@tanstack/react-router';
import type { MouseEvent } from 'react';
import { cn } from '@/shared/components/utils';
import type { ClientDocument } from '@/shared/types/documents';
import type { LatestEvaluationItem } from '@/shared/types/evaluations';
import { getSlmDisplayStatus, type SlmStatusQueryState } from '@/shared/utils/slmDisplayStatus';
import { formatDate, sourceTypeLabels } from '../utils/document.utils';

interface DocumentTableProps {
  documents: ClientDocument[];
  flashId: string | null;
  latestEvalsByDocId?: Record<string, LatestEvaluationItem>;
  latestEvalsState?: SlmStatusQueryState;
}

export function DocumentTable({
  documents,
  flashId,
  latestEvalsByDocId = {},
  latestEvalsState = {},
}: DocumentTableProps) {
  const navigate = useNavigate();

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse border-spacing-0">
        <thead className="border-b border-border bg-surface-subtle">
          <tr>
            <th
              scope="col"
              className="py-2.5 px-6 md:px-8 text-xs font-semibold uppercase tracking-wider text-text-muted w-36"
            >
              Status
            </th>
            <th
              scope="col"
              className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-text-muted w-[35%] min-w-[18rem]"
            >
              Name
            </th>
            <th
              scope="col"
              className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-text-muted w-[25%] min-w-[14rem]"
            >
              Course
            </th>
            <th
              scope="col"
              className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-text-muted w-28"
            >
              Program
            </th>
            <th
              scope="col"
              className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-text-muted w-28"
            >
              Type
            </th>
            <th
              scope="col"
              className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-text-muted w-36"
            >
              Uploaded
            </th>
            <th
              scope="col"
              className="py-2.5 px-6 md:px-8 text-xs font-semibold uppercase tracking-wider text-text-muted text-right w-12"
            >
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-surface">
          {documents.map((document) => {
            const latestEval = latestEvalsByDocId[document.documentId];
            const display = getSlmDisplayStatus(document, latestEval, latestEvalsState);
            const isFlashing = flashId === document.documentId;

            const primaryUrl = display.actionUrl;

            const handleRowClick = (e: MouseEvent<HTMLTableRowElement>) => {
              if ((e.target as HTMLElement).closest('a, button')) {
                return;
              }
              const selection = window.getSelection();
              if (selection && selection.toString().length > 0) {
                return;
              }
              if (display.isClickable && primaryUrl) {
                void navigate({ to: primaryUrl });
              }
            };

            return (
              <tr
                key={document.documentId}
                className={cn(
                  'group transition-colors',
                  isFlashing && 'bg-surface-subtle',
                  display.isClickable && 'cursor-pointer hover:bg-surface-subtle/80',
                  !display.isClickable && 'opacity-75',
                )}
                onClick={display.isClickable && primaryUrl ? handleRowClick : undefined}
              >
                <td className="py-3.5 px-6 md:px-8 w-36">
                  <span
                    className={cn(
                      'inline-flex items-center rounded-xs px-2 py-0.5 text-xs font-semibold tracking-wide select-none',
                      display.badgeClass,
                    )}
                  >
                    {display.showSpinner ? (
                      <Spinner className="mr-1 size-3 animate-spin" aria-hidden="true" />
                    ) : null}
                    {display.badgeLabel}
                  </span>
                </td>
                <td className="py-3.5 px-4 text-sm font-semibold text-text w-[35%] min-w-[18rem]">
                  {display.isClickable && primaryUrl ? (
                    <Link
                      to={primaryUrl}
                      aria-label={display.ariaLabel}
                      className="block truncate font-semibold text-text hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                    >
                      {document.title}
                    </Link>
                  ) : (
                    <span
                      className="block truncate font-semibold text-text-muted cursor-not-allowed"
                      title={display.tooltip}
                    >
                      {document.title}
                    </span>
                  )}
                </td>
                <td className="py-3.5 px-4 text-sm text-text-muted font-medium w-[25%] min-w-[14rem]">
                  <span className="block truncate">{document.courseTitle ?? '—'}</span>
                </td>
                <td className="py-3.5 px-4 text-sm text-text-muted font-medium whitespace-nowrap w-28">
                  {document.program ?? '—'}
                </td>
                <td className="py-3.5 px-4 text-sm text-text-muted font-medium whitespace-nowrap w-28">
                  {sourceTypeLabels[document.sourceType]}
                </td>
                <td className="py-3.5 px-4 text-sm text-text-muted font-medium whitespace-nowrap tabular-nums w-36">
                  {formatDate(document.uploadedAt)}
                </td>
                <td className="py-3.5 px-6 md:px-8 text-right w-12">
                  {display.isClickable && display.actionUrl ? (
                    <Link
                      to={display.actionUrl}
                      aria-label={display.ariaLabel}
                      title={display.actionLabel}
                      className="inline-flex size-8 items-center justify-center rounded-sm text-text-muted hover:text-text hover:bg-surface-subtle transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <CaretRight
                        className="size-4 text-text-muted group-hover:text-text transition-colors"
                        aria-hidden="true"
                      />
                    </Link>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function DocumentTableSkeleton() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse border-spacing-0">
        <thead className="border-b border-border bg-surface-subtle">
          <tr>
            <th
              scope="col"
              className="py-2.5 px-6 md:px-8 text-xs font-semibold uppercase tracking-wider text-text-muted w-36"
            >
              Status
            </th>
            <th
              scope="col"
              className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-text-muted w-[35%] min-w-[18rem]"
            >
              Name
            </th>
            <th
              scope="col"
              className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-text-muted w-[25%] min-w-[14rem]"
            >
              Course
            </th>
            <th
              scope="col"
              className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-text-muted w-28"
            >
              Program
            </th>
            <th
              scope="col"
              className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-text-muted w-28"
            >
              Type
            </th>
            <th
              scope="col"
              className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-text-muted w-36"
            >
              Uploaded
            </th>
            <th
              scope="col"
              className="py-2.5 px-6 md:px-8 text-xs font-semibold uppercase tracking-wider text-text-muted text-right w-12"
            >
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-surface">
          {Array.from({ length: 5 }).map((_, idx) => (
            <tr key={idx} className="animate-pulse">
              <td className="py-4 px-6 w-36">
                <div className="h-5 w-16 bg-surface-subtle border border-border/40 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-[35%] min-w-[18rem]">
                <div className="h-4 w-48 bg-surface-subtle border border-border/40 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-[25%] min-w-[14rem]">
                <div className="h-4 w-36 bg-surface-subtle border border-border/40 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-28">
                <div className="h-4 w-12 bg-surface-subtle border border-border/40 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-28">
                <div className="h-4 w-12 bg-surface-subtle border border-border/40 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-36">
                <div className="h-4 w-20 bg-surface-subtle border border-border/40 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-12" />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
