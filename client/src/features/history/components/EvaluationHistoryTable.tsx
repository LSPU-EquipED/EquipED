import { useState } from 'react';
import { Outlet, Link } from '@tanstack/react-router';
import { ExternalLink, Loader2, TriangleAlert } from 'lucide-react';
import { useEvaluationHistory } from '../hooks/useEvaluationHistory';
import type { HistoryEvaluationItem } from '../types';

const STATUS_OPTIONS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'EVALUATING', label: 'Evaluating' },
  { value: 'SUBMITTED', label: 'Submitted' },
] as const;

function statusBadgeClass(status: string) {
  if (status === 'FAILED') return 'bg-[#b91c1c] text-white';
  if (status.startsWith('COMPLETED')) return 'bg-[#3b963e] text-white';
  if (status === 'EVALUATING') return 'bg-[#1b3b87] text-white';
  return 'bg-[#f2c811] text-[#1e293b]';
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: '2-digit',
    day: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

export function EvaluationHistoryTable() {
  const [status, setStatus] = useState('all');

  const { data, isLoading, isError } = useEvaluationHistory({
    status: status !== 'all' ? status : undefined,
  });

  return (
    <section className="mx-auto grid w-full max-w-[108rem] gap-7">
      {/* Status filter bar */}
      <div className="flex flex-wrap items-center justify-end gap-4">
        <div className="flex items-center gap-3">
          <label
            htmlFor="history-status-filter"
            className="text-xs font-bold uppercase tracking-wider text-slate-500 whitespace-nowrap"
          >
            Filter by status
          </label>
          <select
            id="history-status-filter"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-10 border border-slate-200 bg-white px-3 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-800 cursor-pointer min-w-[10rem]"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table card */}
      <div className="border border-slate-200 bg-white rounded-sm">
        {/* Table meta bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-6 py-4 bg-slate-50/50">
          <p className="text-sm font-medium text-slate-600">
            {isLoading && !data
              ? 'Loading records…'
              : `${data?.total ?? 0} evaluation${(data?.total ?? 0) === 1 ? '' : 's'} found`}
          </p>
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">
            Human review is authoritative.
          </p>
        </div>

        <div className="px-6 py-6">
          {/* Error state */}
          {isError ? (
            <div className="flex items-center gap-2 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm text-[#b91c1c] font-semibold">
              <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
              Failed to load evaluation history.
            </div>
          ) : null}

          {/* Loading state */}
          {isLoading && !data ? (
            <div className="flex justify-center items-center py-12 text-slate-500 font-semibold text-sm gap-2">
              <Loader2 className="size-5 animate-spin text-[#1b3b87]" aria-hidden="true" />
              <span>Loading evaluation history…</span>
            </div>
          ) : null}

          {/* Empty state */}
          {!isError && !isLoading && (!data || data.items.length === 0) ? (
            <div className="grid gap-2 rounded-sm border border-dashed border-slate-200 px-6 py-12 text-center">
              <h3 className="text-lg font-semibold text-slate-800">No evaluations yet</h3>
              <p className="text-sm text-slate-500">
                Evaluations will appear here once you run one from the Documents inventory.
              </p>
            </div>
          ) : null}

          {/* Table */}
          {!isError && data && data.items.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse border-spacing-0">
                <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] tracking-wider font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4 font-semibold text-slate-500 min-w-[20rem]">
                      Document / SLM
                    </th>
                    <th className="py-3 px-4 font-semibold text-slate-500">Status</th>
                    <th className="py-3 px-4 font-semibold text-slate-500">Submitted</th>
                    <th className="py-3 px-4 font-semibold text-slate-500">Completed</th>
                    <th className="py-3 px-4 font-semibold text-slate-500 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {data.items.map((record: HistoryEvaluationItem) => (
                    <tr key={record.evaluation_id} className="hover:bg-slate-50/50">
                      <td className="py-3 px-4 text-sm font-semibold text-slate-900">
                        <div className="flex flex-col gap-0.5">
                          <span className="truncate max-w-[22rem]">
                            {record.document_title ?? '—'}
                          </span>
                          <span className="text-[10px] font-sans tabular-nums font-bold text-slate-400 uppercase tracking-wider">
                            {record.evaluation_id}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm">
                        <span
                          className={`inline-flex items-center rounded-sm px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${statusBadgeClass(record.status)}`}
                        >
                          {record.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm text-slate-600 font-medium">
                        {formatDate(record.submitted_at)}
                      </td>
                      <td className="py-3 px-4 text-sm text-slate-500 font-medium">
                        {record.completed_at ? formatDate(record.completed_at) : '—'}
                      </td>
                      <td className="py-3 px-4 text-sm text-right">
                        <Link
                          to="/evaluations/$id"
                          params={{ id: record.evaluation_id }}
                          className="inline-flex h-8 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-3 rounded-sm text-xs font-bold uppercase tracking-wider transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none"
                        >
                          <span>View</span>
                          <ExternalLink className="size-3 ml-1.5" aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>

      <Outlet />
    </section>
  );
}
