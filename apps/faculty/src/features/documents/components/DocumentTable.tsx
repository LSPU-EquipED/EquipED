import { Spinner } from '@phosphor-icons/react';
import { cn } from '@equiped/ui';
import { TableSkeleton } from '@equiped/ui';
import type { ClientDocument } from '@equiped/types';
import type { LatestEvaluationItem } from '@equiped/types';
import type { TargetAgent } from '@equiped/types';
import { getSlmDisplayStatus, type SlmStatusQueryState } from '@/shared/utils/slmDisplayStatus';
import { formatDate, sourceTypeLabels } from '../utils/document.utils';
import { DocumentActionsMenu } from './DocumentActionsMenu';

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

  return (
    <div className="overflow-x-auto min-w-0 w-full">
      <table className="w-full min-w-[59rem] table-fixed border-collapse border-spacing-0 text-left">
        <caption className="sr-only">Course module inventory</caption>
        <thead className="border-b border-border bg-surface-subtle text-[11px] font-medium tracking-[0.04em] text-text-muted">
          <tr>
            <th
              scope="col"
              className="w-40 min-w-[10rem] py-3 pl-4 pr-3 text-left align-middle sm:pl-6"
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
                  hasMultipleTypes ? 'w-32 min-w-[7rem]' : 'w-32 min-w-[8rem]',
              )}
            >
              Uploaded
            </th>
            <th
              scope="col"
              className="w-28 py-3 pl-2 pr-4 text-right align-middle sm:pr-6"
            >
              Actions
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
                className={cn(
                  isFlashing && 'animate-ledger-flash-decay',
                  !display.isClickable && 'bg-surface-subtle/30',
                )}
              >
                {/* 1. Status */}
                <td className="w-40 min-w-[10rem] whitespace-nowrap py-3 pl-4 pr-3 align-middle sm:pl-6">
                  <span
                    className={cn(
                    'inline-flex items-center rounded-xs px-2 py-0.5 text-xs font-semibold select-none whitespace-nowrap',
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
                    className="block truncate font-semibold text-sm text-text"
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
                <td className="w-28 py-3 pl-2 pr-4 text-right align-middle sm:pr-6">
                  <DocumentActionsMenu
                    document={document}
                    display={display}
                    onInspect={onInspect}
                  />
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
      headerClassName: 'w-40 min-w-[10rem] pl-4 sm:pl-6 pr-3 align-middle',
      cellClassName: 'w-40 min-w-[10rem] pl-4 sm:pl-6 pr-3 align-middle',
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
      headerClassName: hasMultipleTypes ? 'w-32 min-w-[7rem] px-3.5 align-middle' : 'w-32 min-w-[8rem] px-3.5 align-middle',
      cellClassName: hasMultipleTypes ? 'w-32 min-w-[7rem] px-3.5 align-middle' : 'w-32 min-w-[8rem] px-3.5 align-middle',
      skeletonClassName: 'h-4 w-20',
    },
    {
      label: 'Actions',
      headerClassName: 'w-24 min-w-[6rem] pl-2 pr-4 sm:pr-6 text-right align-middle',
      cellClassName: 'w-24 min-w-[6rem] pl-2 pr-4 sm:pr-6 align-middle',
      skeletonClassName: 'size-10 ml-auto',
    },
  ];

  return (
    <TableSkeleton
      ariaLabel="Loading document inventory"
      tableClassName="table-fixed min-w-[59rem]"
      columns={columns}
    />
  );
}
