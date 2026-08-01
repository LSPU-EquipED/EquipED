import { ChevronRight } from 'lucide-react';
import type { KeyboardEvent } from 'react';
import { cn } from '@/shared/components/utils';
import type { ClientDocument } from '@/shared/types/documents';
import { formatDate, getStatusMeta, sourceTypeLabels } from '../utils/document.utils';

interface DocumentTableProps {
  documents: ClientDocument[];
  flashId: string | null;
  onOpenEvaluation: (id: string) => void;
}

export function DocumentTable({ documents, flashId, onOpenEvaluation }: DocumentTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse border-spacing-0">
        <thead className="border-b border-slate-200 bg-slate-50/60">
          <tr>
            <th className="py-2.5 px-6 md:px-8 text-xs font-semibold uppercase tracking-wider text-slate-500 w-32">
              Status
            </th>
            <th className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500 w-[35%] min-w-[18rem]">
              Name
            </th>
            <th className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500 w-[25%] min-w-[14rem]">
              Course
            </th>
            <th className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500 w-28">
              Program
            </th>
            <th className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500 w-28">
              Type
            </th>
            <th className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500 w-36">
              Uploaded
            </th>
            <th className="py-2.5 px-6 md:px-8 text-xs font-semibold uppercase tracking-wider text-slate-500 text-right w-12" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {documents.map((document) => {
            const isReady = document.processingStatus === 'PROCESSED';
            const statusMeta = getStatusMeta(document.processingStatus);
            const isFlashing = flashId === document.documentId;

            return (
              <tr
                key={document.documentId}
                className={cn(
                  'group transition-colors',
                  isFlashing && 'bg-slate-50',
                  isReady && 'cursor-pointer hover:bg-slate-50/80',
                  !isReady && 'opacity-70',
                )}
                {...(isReady
                  ? {
                      role: 'link',
                      tabIndex: 0,
                      onClick: () => onOpenEvaluation(document.documentId),
                      onKeyDown: (e: KeyboardEvent<HTMLTableRowElement>) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onOpenEvaluation(document.documentId);
                        }
                      },
                    }
                  : {})}
              >
                <td className="py-3.5 px-6 md:px-8 w-32">
                  <span
                    className={cn(
                      'inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-semibold uppercase tracking-wider',
                      statusMeta.badgeClass,
                    )}
                  >
                    {statusMeta.icon}
                    {statusMeta.label}
                  </span>
                </td>
                <td className="py-3.5 px-4 text-sm font-semibold text-slate-800 w-[35%] min-w-[18rem]">
                  {isReady ? (
                    <span className="block truncate group-hover:text-slate-600 transition-colors">
                      {document.title}
                    </span>
                  ) : (
                    <span
                      className="block truncate cursor-not-allowed"
                      title={
                        document.processingStatus === 'PENDING'
                          ? 'Processing in progress — check back shortly.'
                          : 'Processing failed. Document is not available for evaluation.'
                      }
                    >
                      {document.title}
                    </span>
                  )}
                </td>
                <td className="py-3.5 px-4 text-sm text-slate-600 font-medium w-[25%] min-w-[14rem]">
                  <span className="block truncate">{document.courseTitle ?? '—'}</span>
                </td>
                <td className="py-3.5 px-4 text-sm text-slate-600 font-medium whitespace-nowrap w-28">
                  {document.program ?? '—'}
                </td>
                <td className="py-3.5 px-4 text-sm text-slate-600 font-medium whitespace-nowrap w-28">
                  {sourceTypeLabels[document.sourceType]}
                </td>
                <td className="py-3.5 px-4 text-sm text-slate-500 font-medium whitespace-nowrap tabular-nums w-36">
                  {formatDate(document.uploadedAt)}
                </td>
                <td className="py-3.5 px-6 md:px-8 text-right w-12">
                  {isReady ? (
                    <ChevronRight
                      className="ml-auto size-4 text-slate-500 group-hover:text-slate-600 transition-colors"
                      aria-hidden="true"
                    />
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
        <thead className="border-b border-slate-200 bg-slate-50/60">
          <tr>
            <th className="py-2.5 px-6 md:px-8 text-xs font-semibold uppercase tracking-wider text-slate-500 w-32">
              Status
            </th>
            <th className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500 w-[35%] min-w-[18rem]">
              Name
            </th>
            <th className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500 w-[25%] min-w-[14rem]">
              Course
            </th>
            <th className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500 w-28">
              Program
            </th>
            <th className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500 w-28">
              Type
            </th>
            <th className="py-2.5 px-4 text-xs font-semibold uppercase tracking-wider text-slate-500 w-36">
              Uploaded
            </th>
            <th className="py-2.5 px-6 md:px-8 text-xs font-semibold uppercase tracking-wider text-slate-500 text-right w-12" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {Array.from({ length: 5 }).map((_, idx) => (
            <tr key={idx} className="animate-pulse">
              <td className="py-4 px-6 w-32">
                <div className="h-5 w-16 bg-slate-200 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-[35%] min-w-[18rem]">
                <div className="h-4 w-48 bg-slate-200 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-[25%] min-w-[14rem]">
                <div className="h-4 w-36 bg-slate-200 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-28">
                <div className="h-4 w-12 bg-slate-200 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-28">
                <div className="h-4 w-12 bg-slate-200 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-36">
                <div className="h-4 w-20 bg-slate-200 rounded-sm" />
              </td>
              <td className="py-4 px-4 w-12" />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
