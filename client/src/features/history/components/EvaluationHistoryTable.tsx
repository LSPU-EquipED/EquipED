import { useState } from 'react';
import { Outlet, Link } from '@tanstack/react-router';
import { Loader2, AlertTriangle, ExternalLink } from 'lucide-react';
import { HistoryFilters } from './HistoryFilters';
import { useEvaluationHistory } from '../hooks/useEvaluationHistory';
import type { HistoryEvaluationItem } from '../types';

function statusClass(status: string) {
  if (status === 'FAILED') return 'border-red-200 text-red-705 bg-red-50';
  if (status.startsWith('COMPLETED')) return 'border-emerald-200 text-emerald-700 bg-emerald-50';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

export function EvaluationHistoryTable() {
  const [status, setStatus] = useState('all');

  const { data, isLoading, isError } = useEvaluationHistory({
    status: status !== 'all' ? status : undefined,
  });

  return (
    <section className="flex flex-col gap-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          History
        </p>
        <h1 className="mt-2 text-2xl font-bold text-slate-900">Evaluation History</h1>
      </div>

      <HistoryFilters status={status} onStatusChange={setStatus} />

      <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
        {isLoading ? (
          <div className="flex justify-center items-center py-12 text-slate-500 font-semibold text-sm gap-2">
            <Loader2 className="size-6 animate-spin text-[#1b3b87]" />
            <span>Loading evaluation history...</span>
          </div>
        ) : isError ? (
          <div className="flex justify-center items-center py-12 text-red-700 font-semibold text-sm gap-2">
            <AlertTriangle className="size-6 text-red-600" />
            <span>Failed to load evaluation history.</span>
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="text-center py-12 text-slate-500 font-semibold text-sm">
            <p>No evaluation records found</p>
          </div>
        ) : (
          <table className="w-full text-left border-collapse border-spacing-0">
            <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] tracking-wider font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-4 font-semibold text-slate-500">Document / SLM Title</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Status</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Submitted</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Completed</th>
                <th className="py-3 px-4 font-semibold text-slate-500 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {data.items.map((evalRecord: HistoryEvaluationItem) => (
                <tr key={evalRecord.evaluation_id} className="hover:bg-slate-50/50">
                  <td className="py-3 px-4 text-sm font-semibold text-slate-900">
                    <div className="flex flex-col">
                      <span>{evalRecord.document_id}</span>
                      <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider mt-0.5">
                        {evalRecord.evaluation_id}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-sm">
                    <span
                      className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold ${statusClass(evalRecord.status)}`}
                    >
                      {evalRecord.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm text-slate-600 font-semibold">
                    {new Date(evalRecord.submitted_at).toLocaleString()}
                  </td>
                  <td className="py-3 px-4 text-sm text-slate-500 font-semibold">
                    {evalRecord.completed_at
                      ? new Date(evalRecord.completed_at).toLocaleString()
                      : '—'}
                  </td>
                  <td className="py-3 px-4 text-sm text-right">
                    <Link
                      to="/evaluations/$id"
                      params={{ id: evalRecord.evaluation_id }}
                      className="inline-flex h-8 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-3 rounded-sm text-xs font-bold uppercase tracking-wider transition-colors focus:ring-2 focus:ring-slate-200 focus:outline-none"
                    >
                      <span>View</span>
                      <ExternalLink className="size-3 ml-1.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Outlet />
    </section>
  );
}
