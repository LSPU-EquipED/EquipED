import { Warning } from '@phosphor-icons/react';
import { getErrorMessage } from '@equiped/api-client';
import { Button } from '@equiped/ui';
import type { ClientDocument, TargetAgent } from '@equiped/types';
import { useFacultyHome } from '../hooks/useFacultyHome';
import { FacultyLaunchpads } from './FacultyLaunchpads';
import { FacultyOperationalLedger } from './FacultyOperationalLedger';

export interface FacultyHomeProps {
  onEvaluate?: (doc: ClientDocument, agent: TargetAgent) => void;
}

export function FacultyHome({ onEvaluate }: FacultyHomeProps = {}) {
  const {
    isLoading,
    isError,
    error,
    stats,
    homeData,
    documents,
    evaluations,
    latestEvalsByDocId,
    latestEvalsState,
    evaluatingTarget,
    setEvaluatingTarget,
    refetch,
  } = useFacultyHome();

  // Normalize documents and evaluations from either direct array or homeData
  const documentsList = documents.length > 0 ? documents : homeData.recentSlms;
  const evaluationsList = evaluations.length > 0 ? evaluations : homeData.recentEvaluations;

  // Accurate metric computations bound to repository stats
  const totalModules = stats.total;
  const readyModules = stats.ready;
  const inProgressCount = stats.processing;
  const actionRequiredCount = stats.failed + homeData.recentIssues.length;

  const handleEvaluate = (doc: ClientDocument, agent: TargetAgent) => {
    if (onEvaluate) {
      onEvaluate(doc, agent);
    } else {
      setEvaluatingTarget({ doc, agent });
    }
  };

  return (
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-6">
      {/* ── 1. Error State ───────────────────────────────────────────── */}
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

      {/* ── 2. Academic Workstation Bento Control Deck ────────────────── */}
      <FacultyLaunchpads
        totalModules={totalModules}
        readyModules={readyModules}
        inProgressCount={inProgressCount}
        actionRequiredCount={actionRequiredCount}
        isLoading={isLoading}
      />

      {/* ── 3. Unified Operational Module Ledger ─────────────────────── */}
      <FacultyOperationalLedger
        evaluations={evaluationsList}
        recentIssues={homeData.recentIssues}
        isLoading={isLoading}
        latestEvalsByDocId={latestEvalsByDocId}
        latestEvalsState={latestEvalsState}
        onEvaluate={handleEvaluate}
        onRefresh={refetch}
      />
    </section>
  );
}
