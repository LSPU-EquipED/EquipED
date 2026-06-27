import { useNavigate } from '@tanstack/react-router';
import { useMemo } from 'react';
import { AlertTriangle, ArrowRight, Plus, Upload } from 'lucide-react';
import { useAdminSummary } from '@/features/admin/hooks/useAdminSummary';
import { useAdminMatrix } from '@/features/admin/hooks/useAdminMatrix';
import type { MonitoringMatrixRow } from '@/features/admin/types';

function statusClass(status: string) {
  if (status === 'FAILED') return 'bg-[#b91c1c] text-white';
  if (status.startsWith('COMPLETED')) return 'bg-[#3b963e] text-white';
  if (status === 'EVALUATING') return 'bg-[#1b3b87] text-white';
  return 'bg-[#f2c811] text-[#1e293b]';
}

export function AdminHomePage() {
  const navigate = useNavigate();
  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useAdminSummary();
  const {
    data: matrixData,
    isLoading: matrixLoading,
    isError: matrixError,
  } = useAdminMatrix({ page_size: 5 });

  const recentActivity = useMemo(() => {
    return matrixData?.items?.slice(0, 5) ?? [];
  }, [matrixData]);

  return (
    <section className="grid gap-8">
      {/* Summary Row */}
      <div className="border border-slate-200 bg-white rounded-sm overflow-hidden">
        <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-slate-200">
          <SummaryItem
            label="Total SLMs"
            value={summary?.total_documents ?? 0}
            isLoading={summaryLoading}
            isError={summaryError}
          />
          <SummaryItem
            label="Active Evaluations"
            value={summary?.active_evaluations ?? 0}
            isLoading={summaryLoading}
            isError={summaryError}
          />
          <SummaryItem
            label="Registered Faculty"
            value={summary?.total_faculty ?? 0}
            isLoading={summaryLoading}
            isError={summaryError}
          />
          <SummaryItem
            label="Failed Evaluations"
            value={summary?.failed_evaluations ?? 0}
            isLoading={summaryLoading}
            isError={summaryError}
            variant="destructive"
          />
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="border border-slate-200 bg-white rounded-sm p-5 flex flex-col gap-4">
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-sm bg-slate-100 border border-slate-200 text-[#1b3b87] shrink-0">
              <Plus className="size-5" />
            </div>
            <div>
              <p className="font-semibold text-slate-800">Create Faculty Account</p>
              <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                Add a new faculty member to the system.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="w-full h-10 inline-flex items-center justify-between border border-slate-200 hover:bg-slate-50 text-slate-700 px-3 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87]"
            onClick={() => navigate({ to: '/admin/users' })}
          >
            Go to user management
            <ArrowRight className="size-4 text-slate-400" />
          </button>
        </div>

        <div className="border border-slate-200 bg-white rounded-sm p-5 flex flex-col gap-4">
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-sm bg-slate-100 border border-slate-200 text-[#1b3b87] shrink-0">
              <Upload className="size-5" />
            </div>
            <div>
              <p className="font-semibold text-slate-800">Upload Reference Document</p>
              <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                Ingest syllabi, rubrics, or curricula.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="w-full h-10 inline-flex items-center justify-between border border-slate-200 hover:bg-slate-50 text-slate-700 px-3 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87]"
            onClick={() => navigate({ to: '/admin/ingest' })}
          >
            Go to ingestion
            <ArrowRight className="size-4 text-slate-400" />
          </button>
        </div>

        <div className="border border-slate-200 bg-white rounded-sm p-5 flex flex-col gap-4">
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-sm bg-slate-100 border border-slate-200 text-[#1b3b87] shrink-0">
              <AlertTriangle className="size-5" />
            </div>
            <div>
              <p className="font-semibold text-slate-800">Review Failures</p>
              <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                Check failed evaluations in the matrix.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="w-full h-10 inline-flex items-center justify-between border border-slate-200 hover:bg-slate-50 text-slate-700 px-3 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87]"
            onClick={() => navigate({ to: '/matrix' })}
          >
            Open monitoring matrix
            <ArrowRight className="size-4 text-slate-400" />
          </button>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="space-y-4">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Recent Activity
            </p>
            <h2 className="mt-1 text-lg font-bold text-slate-900">Latest Evaluations</h2>
          </div>
          <button
            type="button"
            className="inline-flex items-center justify-center text-xs font-bold text-[#1b3b87] hover:underline uppercase tracking-wider transition-colors"
            onClick={() => navigate({ to: '/matrix' })}
          >
            View all
            <ArrowRight className="ml-1 size-4" />
          </button>
        </div>

        <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
          {matrixLoading ? (
            <div className="space-y-2.5 p-5">
              <div className="animate-pulse bg-slate-100 h-8 w-full rounded-sm" />
              <div className="animate-pulse bg-slate-100 h-8 w-full rounded-sm" />
              <div className="animate-pulse bg-slate-100 h-8 w-full rounded-sm" />
            </div>
          ) : matrixError ? (
            <div className="py-12 text-center">
              <p className="text-sm text-[#b91c1c] font-semibold">
                Unable to load recent activity.
              </p>
              <p className="text-xs text-slate-400 mt-1 font-medium">
                Please try refreshing the page.
              </p>
            </div>
          ) : recentActivity.length === 0 ? (
            <div className="py-12 text-center text-slate-500 font-semibold text-sm">
              <p>No recent evaluation activity.</p>
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
                  <th className="py-3 px-4 font-semibold text-slate-500 text-right">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {recentActivity.map((row: MonitoringMatrixRow) => (
                  <tr key={row.evaluation_id} className="hover:bg-slate-50/50">
                    <td className="py-3 px-4 text-sm font-semibold text-slate-900">
                      {row.document_title || 'Untitled SLM'}
                    </td>
                    <td className="py-3 px-4 text-sm text-slate-600 font-medium">
                      {row.program || '—'}
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <span
                        className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold ${statusClass(row.evaluation_status)}`}
                      >
                        {row.evaluation_status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-slate-600 text-right font-sans tabular-nums font-medium">
                      {row.synthesized_score != null ? row.synthesized_score.toFixed(2) : '—'}
                    </td>
                    <td className="py-3 px-4 text-sm text-right">
                      {row.flag_count > 0 ? (
                        <span className="inline-flex items-center justify-center min-w-5 h-5 rounded-full bg-[#f2c811] text-[#1e293b] text-xs font-bold px-1.5">
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
      </div>
    </section>
  );
}

interface SummaryItemProps {
  label: string;
  value: number;
  isLoading: boolean;
  isError: boolean;
  variant?: 'default' | 'destructive';
}

function SummaryItem({ label, value, isLoading, isError, variant = 'default' }: SummaryItemProps) {
  return (
    <div className="px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <div className="mt-1">
        {isLoading ? (
          <div className="animate-pulse bg-slate-100 h-6 w-12 rounded-sm" />
        ) : isError ? (
          <p className="text-sm font-semibold text-[#b91c1c]">Failed</p>
        ) : (
          <p
            className={`text-xl font-bold ${
              variant === 'destructive' && value > 0 ? 'text-[#b91c1c]' : 'text-slate-800'
            }`}
          >
            {value}
          </p>
        )}
      </div>
    </div>
  );
}
