import { Link } from '@tanstack/react-router';
import {
  ArrowLeft,
  Clock,
  FolderOpen,
  GraduationCap,
  Lightbulb,
  ListChecks,
  ShieldCheck,
  Spinner,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES } from '@/shared/constants/theme';
import type { TargetAgent } from '@/shared/types/evaluations';
import { AgentReviewModal } from '../components/AgentReviewModal';
import { EvaluationConfirmModal } from '../components/EvaluationConfirmModal';
import { SpecialistDirectoryView } from '../components/SpecialistDirectoryView';
import { SpecialistLaunchpad } from '../components/SpecialistLaunchpad';
import { SpecialistResultsScoreboard } from '../components/SpecialistResultsScoreboard';
import { useSpecialistWorkspace } from '../hooks/useSpecialistWorkspace';

const ROLE_ICONS: Record<TargetAgent, typeof GraduationCap> = {
  sme: GraduationCap,
  coordinator: ListChecks,
  gad: ShieldCheck,
  itso: Lightbulb,
};

export interface SpecialistScoreboardPageProps {
  agentId?: TargetAgent;
  documentId?: string;
}

export function SpecialistScoreboardPage(props: SpecialistScoreboardPageProps = {}) {
  const {
    validAgent,
    meta,
    routeDocId,
    allQueueItems,
    pendingItems,
    activeItem,
    activeDocument,
    activeDocId,
    latestJob,
    latestJobId,
    isCompleted,
    isEvaluating,
    isLoading,
    isLoadingResults,
    results,
    domainScore,
    showConfirmModal,
    showReviewModal,
    setShowConfirmModal,
    setShowReviewModal,
    handleModalSubmitted,
    handleReviewModalClose,
  } = useSpecialistWorkspace(props);

  const Icon = ROLE_ICONS[validAgent] || GraduationCap;

  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)] bg-canvas">
      {/* ── Top Role Banner ────────────────────────────────── */}
      <header className="border-b border-border bg-surface px-6 py-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 max-w-[108rem] mx-auto">
          <div className="flex items-start gap-3.5">
            <div className="flex size-10 items-center justify-center rounded-sm bg-primary/10 text-primary shrink-0 border border-primary/20">
              <Icon className="size-5" aria-hidden="true" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold tracking-tight text-text">
                  {meta.fullName} Review
                </h1>
                <Badge variant="info">{meta.shortLabel} Specialist</Badge>
              </div>
              <p className="text-xs text-text-muted mt-0.5 max-w-xl leading-relaxed">
                {meta.requirement}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <Link
              to="/evaluations"
              className={cn(
                BUTTON_STYLES.base,
                BUTTON_STYLES.variants.secondary,
                BUTTON_STYLES.sizes.sm,
                'text-xs font-semibold gap-1.5'
              )}
            >
              <Clock className="size-3.5" aria-hidden="true" />
              <span>Evaluation History</span>
            </Link>
          </div>
        </div>
      </header>

      {/* ── Specialist Action Desk Workspace ──────────────────────── */}
      <main className="flex-1 p-6 max-w-[108rem] w-full mx-auto space-y-6">
        {isLoading ? (
          <div className="rounded-md border border-border bg-surface p-12 text-center flex flex-col items-center justify-center space-y-3">
            <Spinner className="size-8 text-primary animate-spin" aria-hidden="true" />
            <p className="text-xs text-text-muted">Loading specialist workspace…</p>
          </div>
        ) : allQueueItems.length === 0 ? (
          /* No SLMs in Storage State */
          <div className="rounded-md border border-border bg-surface p-12 text-center flex flex-col items-center justify-center space-y-3 max-w-xl mx-auto my-8">
            <FolderOpen className="size-10 text-text-muted/50" aria-hidden="true" />
            <h2 className="text-base font-bold text-text">No SLMs in Storage</h2>
            <p className="text-xs text-text-muted max-w-sm">
              Upload course modules in the SLM Storage repository before running specialist evaluations.
            </p>
            <Link
              to="/documents"
              className={cn(
                BUTTON_STYLES.base,
                BUTTON_STYLES.variants.primary,
                BUTTON_STYLES.sizes.sm,
                'text-xs font-semibold mt-2'
              )}
            >
              <span>Go to SLM Storage</span>
            </Link>
          </div>
        ) : !routeDocId ? (
          /* ── 1. FILE DIRECTORY VIEW: /specialists/$agentId ────────────────────────── */
          <SpecialistDirectoryView
            items={pendingItems}
            validAgent={validAgent}
            meta={meta}
          />
        ) : (
          /* ── 2. TARGETED MODULE EVALUATION & SCORECARD: /specialists/$agentId/$documentId ───────────────── */
          <div className="space-y-6">
            {/* Back Navigation Bar */}
            <div className="flex items-center justify-between">
              <Link
                to="/specialists/$agentId"
                params={{ agentId: validAgent }}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-muted hover:text-text transition-colors"
              >
                <ArrowLeft className="size-3.5" aria-hidden="true" />
                <span>Back to {meta.shortLabel} Modules</span>
              </Link>
            </div>

            {isEvaluating ? (
              /* Live Evaluating Progress State */
              <div className="rounded-md border border-info/30 bg-info-soft/30 p-8 sm:p-12 text-center flex flex-col items-center justify-center space-y-4 max-w-2xl mx-auto">
                <div className="flex size-14 items-center justify-center rounded-sm bg-info/10 text-info border border-info/20">
                  <Spinner className="size-7 animate-spin" aria-hidden="true" />
                </div>
                <div className="space-y-1 max-w-md">
                  <h2 className="text-base font-bold text-text">
                    {meta.fullName} Evaluation in Progress
                  </h2>
                  <p className="text-xs text-text-muted leading-relaxed">
                    Analyzing &ldquo;
                    <span className="font-semibold text-text">
                      {activeItem?.title || activeDocument?.title}
                    </span>
                    &rdquo; against the institutional {meta.shortLabel} rubric. Results typically arrive within 20–30 seconds.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="warning" className="flex items-center gap-1.5">
                    <Spinner className="size-3 animate-spin" aria-hidden="true" />
                    <span>Status: {latestJob?.status || 'EVALUATING'}</span>
                  </Badge>
                </div>
              </div>
            ) : isCompleted ? (
              /* Completed State: Full-Width Specialist Results Scoreboard */
              isLoadingResults || !results ? (
                <div className="rounded-md border border-border bg-surface p-12 text-center flex flex-col items-center justify-center space-y-3">
                  <Spinner className="size-8 text-primary animate-spin" aria-hidden="true" />
                  <p className="text-xs text-text-muted">Loading specialist results…</p>
                </div>
              ) : (
                <SpecialistResultsScoreboard
                  validAgent={validAgent}
                  meta={meta}
                  activeItem={activeItem}
                  activeDocument={activeDocument}
                  latestJobId={latestJobId}
                  results={results}
                  domainScore={domainScore}
                  onOpenReviewModal={() => setShowReviewModal(true)}
                  onOpenReevaluateModal={() => setShowConfirmModal(true)}
                />
              )
            ) : (
              /* Unevaluated / READY Launchpad */
              <SpecialistLaunchpad
                activeItem={activeItem}
                activeDocument={activeDocument}
                meta={meta}
                onLaunch={() => setShowConfirmModal(true)}
              />
            )}
          </div>
        )}
      </main>


      {/* ── Confirmation / Re-evaluation Modal ────────────────────────────── */}
      {showConfirmModal && activeDocId && (
        <EvaluationConfirmModal
          documentId={activeDocId}
          documentTitle={activeDocument?.title || activeItem?.title || 'Course Module'}
          detectedProgram={activeDocument?.program || activeItem?.program || null}
          targetAgent={validAgent}
          onClose={() => setShowConfirmModal(false)}
          onSubmitted={handleModalSubmitted}
        />
      )}

      {/* ── Review & Correct Scores Modal ─────────────────────────────────── */}
      {showReviewModal && latestJobId && domainScore && (
        <AgentReviewModal
          agentName={validAgent}
          evaluationId={latestJobId}
          criteria={domainScore.criteria || []}
          onClose={handleReviewModalClose}
        />
      )}
    </div>
  );
}

export default SpecialistScoreboardPage;
