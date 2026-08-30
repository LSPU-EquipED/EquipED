import { ArrowsClockwise, Warning } from '@phosphor-icons/react';
import { getErrorMessage } from '@/shared/api/http';
import { Button } from '@/shared/components/Button';
import { TYPOGRAPHY } from '@/shared/constants/theme';
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border">
        <div>
          <p className={TYPOGRAPHY.labelMuted}>
            LSPU SCC Faculty Workspace
          </p>
          <h1 className={TYPOGRAPHY.headingLg}>Faculty Overview</h1>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => refetch()}
            className="h-9 px-3 text-xs uppercase tracking-wider"
            title="Refresh dashboard data"
          >
            <ArrowsClockwise className="size-3.5" aria-hidden="true" />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Error state */}
      {isError ? (
        <div className="flex items-center justify-between rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-sm text-destructive">
          <div className="flex items-center gap-2.5">
            <Warning className="size-5 shrink-0" aria-hidden="true" />
            <span className="font-semibold">
              {getErrorMessage(error, 'Unable to load workspace data.')}
            </span>
          </div>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => refetch()}
            className="h-8 px-3 text-xs uppercase tracking-wider"
          >
            Retry
          </Button>
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
