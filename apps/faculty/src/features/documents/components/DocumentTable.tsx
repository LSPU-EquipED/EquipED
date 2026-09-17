import { CaretRight, FileText, Spinner } from '@phosphor-icons/react';
import { Link } from '@tanstack/react-router';
import type { MouseEvent, KeyboardEvent } from 'react';
import { cn } from '@equiped/ui';
import { TableSkeleton } from '@equiped/ui';
import type { ClientDocument } from '@equiped/types';
import type { LatestEvaluationItem } from '@equiped/types';
import type { TargetAgent } from '@equiped/types';
import { getSlmDisplayStatus, type SlmStatusQueryState } from '@/shared/utils/slmDisplayStatus';
import { formatDate, sourceTypeLabels } from '../utils/document.utils';

interface DocumentTableProps {
  documents: ClientDocument[];
  flashId: string | null;
  latestEvalsByDocId?: Record<string, LatestEvaluationItem>;
  latestEvalsState?: SlmStatusQueryState;
  targetAgent?: TargetAgent;
  onInspect?: (document: ClientDocument) => void;
}

export function DocumentTable({
  documents,
  flashId,
  latestEvalsByDocId = {},
  latestEvalsState = {},
  targetAgent = 'sme',
  onInspect,
}: DocumentTableProps) {
  const hasMultipleTypes = documents.some((d) => d.sourceType !== 'slm');

  const handleRowClick = (e: MouseEvent<HTMLTableRowElement>, doc: ClientDocument) => {
    // If the user clicked an interactive inner element (link, button, etc.), don't trigger row inspection
    if ((e.target as HTMLElement).closest('a, button, details')) {
      return;
    }
    // Prevent opening if the user is selecting text to copy
    const selection = window.getSelection();
    if (selection && selection.toString().length > 0) {
      return;
    }
    onInspect?.(doc);
  };

  const handleRowKeyDown = (e: KeyboardEvent<HTMLTableRowElement>, doc: ClientDocument) => {
    if (e.key === 'Enter' || e.key === ' ') {
      if ((e.target as HTMLElement).closest('a, button, details')) {
        return;
      }
      e.preventDefault();
      onInspect?.(doc);
    }
  };

  return (
    <div className="overflow-x-auto min-w-0 w-full">
      <table className="w-full text-left border-collapse border-spacing-0 min-w-[60rem] table-fixed">
        <caption className="sr-only">Course Modules and Indexed Content repository ledger</caption>
        <thead className="border-b border-border bg-surface-subtle text-xs font-semibold text-text-muted">
          <tr>
            <th
              scope="col"
              className="py-3 pl-4 sm:pl-6 pr-3 text-left align-middle w-44 min-w-[11rem]"
            >
              Status
            </th>
            <th
              scope="col"
              className={cn(
                'py-3 px-3.5 text-left align-middle',
                hasMultipleTypes ? 'w-[32%] min-w-[16rem]' : 'w-[36%] min-w-[16rem]',
              )}
            >
              Module Name
            </th>
            <th
              scope="col"
              className={cn(
                'py-3 px-3.5 text-left align-middle',
                hasMultipleTypes ? 'w-[24%] min-w-[12rem]' : 'w-[28%] min-w-[13rem]',
              )}
            >
              Course
            </th>
            <th
              scope="col"
              className="py-3 px-3.5 text-left align-middle w-28 min-w-[6.5rem]"
            >
              Program
            </th>
            {hasMultipleTypes && (
              <th
                scope="col"
                className="py-3 px-3.5 text-left align-middle w-28 min-w-[6.5rem]"
              >
                Type
              </th>
            )}
            <th
              scope="col"
              className={cn(
                'py-3 px-3.5 text-left align-middle',
                hasMultipleTypes ? 'w-32 min-w-[7.5rem]' : 'w-36 min-w-[8.5rem]',
              )}
            >
              Uploaded
            </th>
            <th
              scope="col"
              className="py-3 pl-2 pr-4 sm:pr-6 text-right align-middle w-24 min-w-[6rem]"
            >
              Action
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border bg-surface">
          {documents.map((document) => {
            const latestEval = latestEvalsByDocId[document.documentId];
            const display = getSlmDisplayStatus(
              document,
              latestEval,
              latestEvalsState,
              targetAgent,
            );
            const isFlashing = flashId === document.documentId;

            return (
              <tr
                key={document.documentId}
                tabIndex={onInspect ? 0 : undefined}
                role={onInspect ? 'button' : undefined}
                aria-label={onInspect ? `View details for ${document.title}` : undefined}
                onKeyDown={onInspect ? (e) => handleRowKeyDown(e, document) : undefined}
                onClick={onInspect ? (e) => handleRowClick(e, document) : undefined}
                className={cn(
                  'group transition-colors',
                  isFlashing && 'animate-ledger-flash-decay',
                  onInspect && 'cursor-pointer hover:bg-surface-subtle/70 focus-visible:outline-none focus-visible:bg-surface-subtle/80',
                  !display.isClickable && 'opacity-75',
                )}
              >
                {/* 1. Status */}
                <td className="py-3 pl-4 sm:pl-6 pr-3 align-middle w-44 min-w-[11rem]">
                  <span
                    className={cn(
                      'inline-flex items-center rounded-xs px-2 py-0.5 text-xs font-semibold tracking-wide select-none whitespace-nowrap',
                      display.badgeClass,
                    )}
                  >
                    {display.showSpinner ? (
                      <Spinner className="mr-1 size-3 animate-spin" aria-hidden="true" />
                    ) : null}
                    {display.badgeLabel}
                  </span>
                </td>

                {/* 2. Module Name */}
                <td
                  className={cn(
                    'py-3 px-3.5 align-middle',
                    hasMultipleTypes ? 'w-[32%] min-w-[16rem]' : 'w-[36%] min-w-[16rem]',
                  )}
                >
                  <span
                    className="block truncate font-semibold text-sm text-text group-hover:text-primary transition-colors"
                    title={document.title}
                  >
                    {document.title}
                  </span>
                </td>

                {/* 3. Course */}
                <td
                  className={cn(
                    'py-3 px-3.5 align-middle',
                    hasMultipleTypes ? 'w-[24%] min-w-[12rem]' : 'w-[28%] min-w-[13rem]',
                  )}
                >
                  <span
                    className="block truncate text-xs sm:text-sm text-text-muted font-medium"
                    title={[document.courseCode, document.courseTitle].filter(Boolean).join(' — ') || undefined}
                  >
                    {document.courseCode
                      ? document.courseTitle
                        ? `${document.courseCode} — ${document.courseTitle}`
                        : document.courseCode
                      : document.courseTitle ?? 'Not specified'}
                  </span>
                </td>

                {/* 4. Program */}
                <td className="py-3 px-3.5 align-middle w-28 min-w-[6.5rem]">
                  {document.program ? (
                    <span className="inline-flex items-center rounded-xs border border-border bg-surface-subtle px-1.5 py-0.5 font-mono text-[11px] font-semibold text-text select-none">
                      {document.program}
                    </span>
                  ) : (
                    <span className="text-text-muted/60 select-none font-mono text-xs">Not specified</span>
                  )}
                </td>

                {/* 5. Type (conditionally rendered only if multiple types exist) */}
                {hasMultipleTypes && (
                  <td className="py-3 px-3.5 align-middle text-xs text-text-muted font-medium whitespace-nowrap w-28 min-w-[6.5rem]">
                    {sourceTypeLabels[document.sourceType]}
                  </td>
                )}

                {/* 6. Uploaded */}
                <td
                  className={cn(
                    'py-3 px-3.5 align-middle text-xs text-text-muted font-medium whitespace-nowrap tabular-nums',
                    hasMultipleTypes ? 'w-32 min-w-[7.5rem]' : 'w-36 min-w-[8.5rem]',
                  )}
                >
                  {formatDate(document.uploadedAt)}
                </td>

                {/* 7. Actions */}
                <td className="py-3 pl-2 pr-4 sm:pr-6 align-middle text-right w-24 min-w-[6rem]">
                  <div className="flex items-center justify-end gap-1.5">
                    {/* Document Icon (Open PDF with tooltip) */}
                    <a
                      href={`/api/v1/documents/${document.documentId}/file`}
                      target="_blank"
                      rel="noopener noreferrer"
                      title="Open PDF"
                      aria-label={`Open ${document.title} PDF`}
                      className="inline-flex size-7 items-center justify-center rounded-sm text-text-muted hover:text-text hover:bg-surface-subtle transition-all active:scale-95 cursor-pointer border border-transparent hover:border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <FileText className="size-3.5" aria-hidden="true" />
                    </a>

                    {/* Launch / View Evaluation Action */}
                    {display.isClickable && display.actionUrl ? (
                      <Link
                        to={display.actionUrl}
                        aria-label={display.ariaLabel}
                        title={display.actionLabel}
                        className="inline-flex size-7 items-center justify-center rounded-sm text-text-muted hover:text-text hover:bg-surface-subtle transition-all active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring border border-transparent hover:border-border"
                      >
                        <CaretRight
                          className="size-4 text-text-muted group-hover:text-text transition-colors"
                          aria-hidden="true"
                        />
                      </Link>
                    ) : null}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function DocumentTableSkeleton({ hasMultipleTypes = false }: { hasMultipleTypes?: boolean }) {
  const columns = [
    {
      label: 'Status',
      headerClassName: 'w-44 min-w-[11rem] pl-4 sm:pl-6 pr-3 align-middle',
      cellClassName: 'w-44 min-w-[11rem] pl-4 sm:pl-6 pr-3 align-middle',
      skeletonClassName: 'h-5 w-24',
    },
    {
      label: 'Module Name',
      headerClassName: hasMultipleTypes ? 'w-[32%] min-w-[16rem] px-3.5 align-middle' : 'w-[36%] min-w-[16rem] px-3.5 align-middle',
      cellClassName: hasMultipleTypes ? 'w-[32%] min-w-[16rem] px-3.5 align-middle' : 'w-[36%] min-w-[16rem] px-3.5 align-middle',
      skeletonClassName: 'h-4 w-48',
    },
    {
      label: 'Course',
      headerClassName: hasMultipleTypes ? 'w-[24%] min-w-[12rem] px-3.5 align-middle' : 'w-[28%] min-w-[13rem] px-3.5 align-middle',
      cellClassName: hasMultipleTypes ? 'w-[24%] min-w-[12rem] px-3.5 align-middle' : 'w-[28%] min-w-[13rem] px-3.5 align-middle',
      skeletonClassName: 'h-4 w-36',
    },
    {
      label: 'Program',
      headerClassName: 'w-28 min-w-[6.5rem] px-3.5 align-middle',
      cellClassName: 'w-28 min-w-[6.5rem] px-3.5 align-middle',
      skeletonClassName: 'h-5 w-14',
    },
    ...(hasMultipleTypes
      ? [
          {
            label: 'Type',
            headerClassName: 'w-28 min-w-[6.5rem] px-3.5 align-middle',
            cellClassName: 'w-28 min-w-[6.5rem] px-3.5 align-middle',
            skeletonClassName: 'h-4 w-20',
          },
        ]
      : []),
    {
      label: 'Uploaded',
      headerClassName: hasMultipleTypes ? 'w-32 min-w-[7.5rem] px-3.5 align-middle' : 'w-36 min-w-[8.5rem] px-3.5 align-middle',
      cellClassName: hasMultipleTypes ? 'w-32 min-w-[7.5rem] px-3.5 align-middle' : 'w-36 min-w-[8.5rem] px-3.5 align-middle',
      skeletonClassName: 'h-4 w-20',
    },
    {
      label: 'Action',
      headerClassName: 'w-24 min-w-[6rem] pl-2 pr-4 sm:pr-6 text-right align-middle',
      cellClassName: 'w-24 min-w-[6rem] pl-2 pr-4 sm:pr-6 align-middle',
      skeletonClassName: 'h-7 w-16 ml-auto',
    },
  ];

  return (
    <TableSkeleton
      ariaLabel="Loading document inventory"
      tableClassName="table-fixed min-w-[60rem]"
      columns={columns}
    />
  );
}
