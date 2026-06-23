import { useState } from 'react';
import { Loader2, AlertTriangle } from 'lucide-react';
import { MatrixFilters } from './MatrixFilters';
import { useMonitoringMatrix } from '../hooks/useMonitoringMatrix';
import type { MonitoringMatrixRow } from '../types';

function statusClass(status: string) {
  if (status === 'FAILED') return 'border-red-200 text-red-700 bg-red-50';
  if (status.startsWith('COMPLETED')) return 'border-emerald-200 text-emerald-700 bg-emerald-50';
  return 'border-slate-200 bg-slate-50 text-slate-600';
}

export function MonitoringTable() {
  const [program, setProgram] = useState('all');
  const [status, setStatus] = useState('all');

  const { data, isLoading, isError } = useMonitoringMatrix({
    program: program !== 'all' ? program : undefined,
    status: status !== 'all' ? status : undefined,
  });

  return (
    <section className="flex flex-col gap-6">

      <MatrixFilters
        program={program}
        status={status}
        onProgramChange={setProgram}
        onStatusChange={setStatus}
      />

      <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
        {isLoading ? (
          <div className="flex justify-center items-center py-12 text-slate-500 font-semibold text-sm gap-2">
            <Loader2 className="size-6 animate-spin text-[#1b3b87]" />
            <span>Loading matrix data...</span>
          </div>
        ) : isError ? (
          <div className="flex justify-center items-center py-12 text-red-700 font-semibold text-sm gap-2">
            <AlertTriangle className="size-6 text-red-600" />
            <span>Failed to load matrix data.</span>
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="text-center py-12 text-slate-500 font-semibold text-sm">
            <p>No evaluation records yet</p>
          </div>
        ) : (
          <table className="w-full text-left border-collapse border-spacing-0">
            <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] tracking-wider font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-4 font-semibold text-slate-500">SLM Title</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Program</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Status</th>
                <th className="py-3 px-4 font-semibold text-slate-500 text-right">Score</th>
                <th className="py-3 px-4 font-semibold text-slate-500 text-right">Flags</th>
                <th className="py-3 px-4 font-semibold text-slate-500 text-right">Last Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {data.items.map((row: MonitoringMatrixRow) => (
                <tr key={row.evaluation_id} className="hover:bg-slate-50/50">
                  <td className="py-3 px-4 text-sm font-semibold text-slate-900">
                    {row.document_title || 'Untitled SLM'}
                  </td>
                  <td className="py-3 px-4 text-sm text-slate-600 font-medium">{row.program || '—'}</td>
                  <td className="py-3 px-4 text-sm">
                    <span
                      className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold ${statusClass(row.evaluation_status)}`}
                    >
                      {row.evaluation_status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm text-slate-600 text-right font-mono font-medium">
                    {row.synthesized_score != null ? row.synthesized_score.toFixed(2) : '—'}
                  </td>
                  <td className="py-3 px-4 text-sm text-right">
                    {row.flag_count > 0 ? (
                      <span className="inline-flex items-center justify-center min-w-5 h-5 rounded-full bg-orange-100 text-orange-700 text-xs font-bold px-1.5">
                        {row.flag_count}
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-sm text-right text-slate-500 font-semibold">
                    {new Date(row.last_updated).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
