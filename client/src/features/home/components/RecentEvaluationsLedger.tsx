import { Link } from '@tanstack/react-router';
import { ArrowRight, ClipboardList, ExternalLink } from 'lucide-react';
import { cn } from '@/shared/components/utils';
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
    <div className="rounded-sm border border-slate-200 bg-white overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/60 px-5 py-3.5">
        <div className="flex items-center gap-2">
          <ClipboardList className="size-4 text-[#1b3b87]" aria-hidden="true" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
            Recent Evaluations
          </h2>
        </div>
        <Link
          to="/evaluations"
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
        ) : evaluations.length === 0 ? (
          <div className="p-8 text-center flex flex-col items-center justify-center">
            <ClipboardList className="size-8 text-slate-300 mb-2" aria-hidden="true" />
            <p className="text-sm font-semibold text-slate-700">No evaluations yet</p>
            <p className="text-xs text-slate-500 mt-1 max-w-xs">
              Evaluations will appear here after you evaluate an SLM.
            </p>
            <Link
              to="/documents"
              className="mt-4 inline-flex items-center gap-2 rounded-sm border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold uppercase tracking-wider text-slate-700 hover:bg-slate-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
            >
              <span>Go to My SLMs</span>
              <ArrowRight className="size-3.5 text-slate-500" aria-hidden="true" />
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead className="border-b border-slate-100 bg-slate-50/40 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th scope="col" className="py-2.5 px-4">Document / Evaluation</th>
                  <th scope="col" className="py-2.5 px-3">Status</th>
                  <th scope="col" className="py-2.5 px-3">Submitted</th>
                  <th scope="col" className="py-2.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {evaluations.map((ev) => {
                  const badge = getEvaluationStatusBadge(ev.status);

                  return (
                    <tr key={ev.evaluation_id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3 px-4 font-semibold text-slate-900 max-w-[14rem]">
                        <div className="truncate" title={ev.document_title || ev.evaluation_id}>
                          {ev.document_title || 'Untitled SLM'}
                        </div>
                        <div className="text-[10px] font-mono text-slate-500 truncate">
                          {ev.evaluation_id}
                        </div>
                      </td>
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span
                          className={cn(
                            'inline-flex rounded-sm px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                            badge.className,
                          )}
                        >
                          {badge.label}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-500 whitespace-nowrap tabular-nums">
                        {formatDateOnly(ev.submitted_at)}
                      </td>
                      <td className="py-3 px-4 text-right whitespace-nowrap">
                        <Link
                          to="/evaluations/$id"
                          params={{ id: ev.evaluation_id }}
                          className="inline-flex h-7 items-center gap-1 rounded-sm border border-slate-200 bg-white px-2.5 text-[11px] font-bold uppercase tracking-wider text-slate-700 hover:bg-slate-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
                        >
                          <span>View</span>
                          <ExternalLink className="size-3 text-slate-500" aria-hidden="true" />
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
