import { Loader2 } from 'lucide-react';
import { usePreferenceLogs } from '../hooks/usePreferenceLogs';
import type { PreferenceLogItem } from '../types';

function actionClass(action: string) {
  return action === 'EDITED'
    ? 'border-[#1b3b87]/50 text-[#1b3b87] bg-[#1b3b87]/10'
    : 'border-slate-200 bg-slate-50 text-slate-600';
}

export function PreferenceLogTable() {
  const { data, isLoading, isError } = usePreferenceLogs();

  return (
    <section className="grid gap-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          Admin
        </p>
        <h1 className="mt-2 text-2xl font-bold text-slate-900">Preference Logs</h1>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-slate-500 font-semibold text-sm">
            <Loader2 className="size-5 animate-spin" /> Loading preference logs...
          </div>
        ) : isError ? (
          <div className="py-10 text-center text-red-750 font-semibold text-sm">Failed to load preference logs.</div>
        ) : !data?.items.length ? (
          <div className="py-10 text-center text-slate-550 font-semibold text-sm">No preference logs yet.</div>
        ) : (
          <table className="w-full text-left border-collapse border-spacing-0">
            <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] tracking-wider font-semibold border-b border-slate-200">
              <tr>
                <th className="py-3 px-4 font-semibold text-slate-500">User</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Action</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Evaluation</th>
                <th className="py-3 px-4 font-semibold text-slate-500">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {data.items.map((log: PreferenceLogItem) => (
                <tr key={log.log_id} className="hover:bg-slate-50/50">
                  <td className="py-3 px-4 text-sm font-mono text-slate-800">{log.user_id}</td>
                  <td className="py-3 px-4 text-sm">
                    <span
                      className={`inline-flex rounded-sm border px-2 py-0.5 text-xs font-semibold ${actionClass(log.action)}`}
                    >
                      {log.action}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm font-mono text-slate-800">{log.evaluation_id}</td>
                  <td className="py-3 px-4 text-sm text-slate-500 font-semibold">
                    {new Date(log.created_at).toLocaleString()}
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
