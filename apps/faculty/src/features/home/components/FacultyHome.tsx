import { Warning } from '@phosphor-icons/react';
import { getErrorMessage } from '@equiped/api-client';
import { Button } from '@equiped/ui';
import { useFacultyHome } from '../hooks/useFacultyHome';
import { FacultyActiveEvaluationBanner } from './FacultyActiveEvaluationBanner';
import { FacultyLaunchpads } from './FacultyLaunchpads';
import { FacultyOperationalLedger } from './FacultyOperationalLedger';
import { FacultyPulseStrip } from './FacultyPulseStrip';

export interface FacultyHomeProps {
  evaluatorPermissions?: readonly string[] | null;
  userRole?: string;
}

export function FacultyHome({
  evaluatorPermissions,
  userRole,
}: FacultyHomeProps = {}) {
  const {
    isLoading,
    isError,
    error,
    stats,
    homeData,
    evaluations,
    refetch,
  } = useFacultyHome();

  const evaluationsList = evaluations.length > 0 ? evaluations : homeData.recentEvaluations;

  // Accurate metric computations bound to repository stats
  const totalModules = stats.total;
  const readyModules = stats.ready;
  const inProgressCount = stats.processing;
  const actionRequiredCount = stats.failed + homeData.recentIssues.length;

  return (
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-6">
      {/* ── 1. Error State Alert ─────────────────────────────────────── */}
      {isError ? (
        <div
          className="flex items-center justify-between rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-sm text-destructive"
          role="alert"
        >
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
            className="h-8 px-3 text-xs"
          >
            Retry
          </Button>
        </div>
      ) : null}

      {/* ── 2. Real-Time Active Evaluation Docket ────────────────────── */}
      <FacultyActiveEvaluationBanner evaluation={homeData.activeEvaluation} />

      {/* ── 3. Full-Width Repository Pulse Strip ─────────────────────── */}
      <FacultyPulseStrip
        totalModules={totalModules}
        readyModules={readyModules}
        inProgressCount={inProgressCount}
        actionRequiredCount={actionRequiredCount}
        isLoading={isLoading}
      />

      {/* ── 4. Academic Workstation Launchpads ───────────────────────── */}
      <FacultyLaunchpads
        evaluatorPermissions={evaluatorPermissions}
        userRole={userRole}
      />

      {/* ── 5. Unified Faculty Command Ledger ───────────────────────── */}
      <FacultyOperationalLedger
        evaluations={evaluationsList}
        recentIssues={homeData.recentIssues}
        isLoading={isLoading}
        onRefresh={refetch}
      />
    </section>
  );
}
