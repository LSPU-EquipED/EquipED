import { useNavigate } from '@tanstack/react-router';
import { Warning } from '@phosphor-icons/react';
import { getErrorMessage } from '@/shared/api/http';
import { Button } from '@/shared/components/Button';
import { useFacultyHome } from '../hooks/useFacultyHome';
import { FacultyLaunchpads } from './FacultyLaunchpads';
import { FacultyOperationalLedger } from './FacultyOperationalLedger';
import { EvaluationConfirmModal } from '@/features/evaluation/components/EvaluationConfirmModal';

export function FacultyHome() {
  const navigate = useNavigate();

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
        onEvaluate={(doc, agent) => setEvaluatingTarget({ doc, agent })}
        onRefresh={refetch}
      />

      {/* ── 5. In-Place Targeted Evaluation Modal ───────────────────── */}
      {evaluatingTarget && (
        <EvaluationConfirmModal
          documentId={evaluatingTarget.doc.documentId}
          documentTitle={evaluatingTarget.doc.title}
          detectedProgram={evaluatingTarget.doc.program ?? null}
          targetAgent={evaluatingTarget.agent}
          onClose={() => setEvaluatingTarget(null)}
          onSubmitted={(evalId) => {
            setEvaluatingTarget(null);
            void navigate({
              to: '/specialists/$agentId/$documentId',
              params: {
                agentId: evaluatingTarget.agent,
                documentId: evaluatingTarget.doc.documentId,
              },
            });
          }}
        />
      )}
    </section>
  );
}
