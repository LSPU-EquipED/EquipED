import { Link } from '@tanstack/react-router';
import { ArrowRight, FileText, Loader2, PlayCircle } from 'lucide-react';
import type { ClientDocument } from '@/shared/types/documents';
import type { LatestEvaluationItem } from '@/shared/types/evaluations';
import { cn } from '@/shared/components/utils';
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
    <div className="rounded-sm border border-slate-200 bg-white overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/60 px-5 py-3.5">
        <div className="flex items-center gap-2">
          <FileText className="size-4 text-[#1b3b87]" aria-hidden="true" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
            Recent SLMs
          </h2>
        </div>
        <Link
          to="/documents"
          className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wider text-[#1b3b87] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87] rounded-sm"
        >
          <span>View All</span>
          <ArrowRight className="size-3 text-[#1b3b87]" aria-hidden="true" />
        </Link>
      </div>

      {/* Content */}
      <div className="flex-1">
        {isLoading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded-sm bg-slate-100" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="p-8 text-center flex flex-col items-center justify-center">
            <FileText className="size-8 text-slate-300 mb-2" aria-hidden="true" />
            <p className="text-sm font-semibold text-slate-700">No SLMs uploaded yet</p>
            <p className="text-xs text-slate-500 mt-1 max-w-xs">
              Use the Upload SLM action above to add course learning materials.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead className="border-b border-slate-100 bg-slate-50/40 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th scope="col" className="py-2.5 px-4">Title</th>
                  <th scope="col" className="py-2.5 px-3">Program</th>
                  <th scope="col" className="py-2.5 px-3">Status</th>
                  <th scope="col" className="py-2.5 px-3">Uploaded</th>
                  <th scope="col" className="py-2.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {documents.map((doc) => {
                  const latestEval = latestEvalsByDocId[doc.documentId];
                  const display = getSlmDisplayStatus(doc, latestEval, latestEvalsState);
                  const actionUrl = display.actionUrl;

                  return (
                    <tr key={doc.documentId} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3 px-4 font-semibold text-slate-900 max-w-[14rem]">
                        <div className="truncate" title={doc.title}>
                          {doc.title}
                        </div>
                        {doc.courseTitle && (
                          <div className="text-[11px] font-normal text-slate-500 truncate">
                            {doc.courseTitle}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-3 font-medium text-slate-600 whitespace-nowrap">
                        {doc.program || '—'}
                      </td>
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span
                          className={cn(
                            'inline-flex items-center rounded-sm px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                            display.badgeClass,
                          )}
                        >
                          {display.showSpinner ? (
                            <Loader2 className="mr-1 size-3 animate-spin" aria-hidden="true" />
                          ) : null}
                          {display.badgeLabel}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-500 whitespace-nowrap tabular-nums">
                        {formatDateOnly(doc.uploadedAt)}
                      </td>
                      <td className="py-3 px-4 text-right whitespace-nowrap">
                        {display.isClickable && actionUrl ? (
                          <Link
                            to={actionUrl}
                            aria-label={display.ariaLabel}
                            className="inline-flex h-7 items-center gap-1 rounded-sm bg-[#1b3b87] px-2.5 text-[11px] font-bold uppercase tracking-wider text-white hover:bg-[#1b3b87]/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
                          >
                            {display.actionType === 'start_evaluation' ? (
                              <PlayCircle className="size-3" aria-hidden="true" />
                            ) : null}
                            <span>{display.actionLabel}</span>
                          </Link>
                        ) : (
                          <span className="text-[11px] text-slate-500 font-medium">
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
