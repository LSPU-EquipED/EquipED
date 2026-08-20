import { AlertTriangle, RefreshCw } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { useFacultyHome } from '../hooks/useFacultyHome';
import { ActiveEvaluationBanner } from './ActiveEvaluationBanner';
import { AttentionLedger } from './AttentionLedger';
import { RecentSlmsLedger } from './RecentSlmsLedger';
import { RecentEvaluationsLedger } from './RecentEvaluationsLedger';
import { HomeQuickActions } from './HomeQuickActions';

export function FacultyHome() {
  const {
    isLoading,
    isError,
    error,
    homeData,
    latestEvalsByDocId,
    latestEvalsState,
    refetch,
  } = useFacultyHome();

  return (
    <section className="px-6 py-7 max-w-[108rem] mx-auto space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
            LSPU SCC Faculty Workspace
          </p>
          <h1 className="text-xl font-bold text-slate-900 mt-0.5">Faculty Overview</h1>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex h-9 items-center gap-1.5 rounded-sm border border-slate-200 bg-white px-3 text-xs font-bold uppercase tracking-wider text-slate-700 hover:bg-slate-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
            title="Refresh dashboard data"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Error state */}
      {isError ? (
        <div className="flex items-center justify-between rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 p-4 text-sm text-[#b91c1c]">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="size-5 shrink-0" aria-hidden="true" />
            <span className="font-semibold">
              {getErrorMessage(error, 'Unable to load workspace data.')}
            </span>
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            className="rounded-sm bg-[#b91c1c] px-3 py-1 text-xs font-bold uppercase tracking-wider text-white hover:bg-[#b91c1c]/90 transition-colors"
          >
            Retry
          </button>
        </div>
      ) : null}

      {/* Quick Actions */}
      <HomeQuickActions />

      {/* Active Evaluation / Ready Banner */}
      <ActiveEvaluationBanner homeData={homeData} />

      {/* Recent Issues (if failures exist) */}
      <AttentionLedger items={homeData.recentIssues} />

      {/* Two-Column Recent Activity Ledger */}
      <div className="grid gap-6 lg:grid-cols-2">
        <RecentSlmsLedger
          documents={homeData.recentSlms}
          isLoading={isLoading}
          latestEvalsByDocId={latestEvalsByDocId}
          latestEvalsState={latestEvalsState}
        />
        <RecentEvaluationsLedger
          evaluations={homeData.recentEvaluations}
          isLoading={isLoading}
        />
      </div>
    </section>
  );
}
