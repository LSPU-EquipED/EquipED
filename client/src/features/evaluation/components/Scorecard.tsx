import { useMemo, useState } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowsClockwise,
  BookOpen,
  CaretRight,
  CheckCircle,
  Clock,
  FileText,
  Lightbulb,
  Scales,
  ShieldCheck,
  Spinner,
  WarningCircle,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { Skeleton } from '@/shared/components/Skeleton';
import { TABLE_STYLES, TYPOGRAPHY } from '@/shared/constants/theme';
import { isTargetAgent, TARGET_AGENT_META } from '@/shared/types/evaluations';
import { useEvaluation } from '../hooks/useEvaluationStatus';
import { evaluationApi } from '../api/evaluation.api';
import {
  formatScore,
  cleanJustification,
  overallScoreDisplay,
  monitoringPercentage,
} from '../utils/scoreHelpers';
import { ScorecardPdfExport } from './ScorecardPdfExport';
import { AgentReviewModal } from './AgentReviewModal';
import { SpecialistExportDownloadButton } from './ExportDocument';
import { EvaluationConfirmModal } from './EvaluationConfirmModal';

function getAdjectivalRatingClasses(rating: string | undefined): string {
  switch (rating) {
    case 'Very Satisfactory':
      return 'bg-success-soft text-success border-success/30';
    case 'Satisfactory':
      return 'bg-info-soft text-info border-info/30';
    case 'Needs Improvement':
      return 'bg-warning-soft text-warning border-warning/30';
    case 'Poor':
      return 'bg-destructive-soft text-destructive border-destructive/30';
    default:
      return 'bg-surface-subtle text-text-muted border-border';
  }
}

function formatDuration(seconds?: number | null): string {
  if (seconds == null) return '';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

const DOMAIN_ICONS: Record<string, typeof Lightbulb> = {
  sme: Lightbulb,
  coordinator: BookOpen,
  gad: Scales,
  itso: ShieldCheck,
};

function ScorecardSkeleton() {
  return (
    <section
      className="flex h-[calc(100vh-4rem)] min-h-0 flex-col bg-canvas"
      role="status"
      aria-label="Loading evaluation scorecard"
    >
      <header className="flex min-h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-surface px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-4 w-48 max-w-[45vw]" />
        </div>
        <Skeleton className="h-8 w-28" />
      </header>
      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[22rem_minmax(0,1fr)] xl:grid-cols-[26rem_minmax(0,1fr)]">
        <aside className="hidden space-y-5 border-r border-border bg-surface p-5 lg:block">
          <div className="space-y-3 rounded-md border border-border bg-surface-subtle p-4">
            <Skeleton className="h-2.5 w-36" />
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-3 w-40" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-2.5 w-28" />
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-12 w-full" />
            ))}
          </div>
        </aside>
        <main className="min-w-0 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-4xl space-y-5">
            <div className="flex items-center justify-between border-b border-border pb-4">
              <div className="space-y-2">
                <Skeleton className="h-2.5 w-28" />
                <Skeleton className="h-6 w-64 max-w-[60vw]" />
              </div>
              <Skeleton className="size-10 rounded-sm" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="space-y-3 border border-border p-4">
                  <Skeleton className="h-2.5 w-28" />
                  <Skeleton className="h-7 w-20" />
                  <Skeleton className="h-3 w-full" />
                </div>
              ))}
            </div>
            <div className="space-y-4 border border-border p-5">
              <Skeleton className="h-4 w-48" />
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="grid grid-cols-[minmax(0,1fr)_8rem] gap-4">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-20 ml-auto" />
                </div>
              ))}
            </div>
          </div>
        </main>
      </div>
    </section>
  );
}

export function Scorecard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { id } = useParams({ strict: false }) as { id?: string };
  const [selectedDomainId, setSelectedDomainId] = useState<string>('sme');

  const { data: evaluation, isLoading, isError } = useEvaluation(id ?? '');
  const [reviewModalAgent, setReviewModalAgent] = useState<string | null>(null);
  const [showReevaluateModal, setShowReevaluateModal] = useState(false);
  const isTerminal = evaluation?.status === 'COMPLETED' || evaluation?.status === 'FAILED';
  const isFailed = evaluation?.status === 'FAILED';
  const isEvaluating =
    evaluation?.status === 'SUBMITTED' ||
    evaluation?.status === 'PREPROCESSING' ||
    evaluation?.status === 'EVALUATING' ||
    evaluation?.status === 'SYNTHESIZING';
  const {
    data: results,
    isLoading: isLoadingResults,
    isError: isResultsError,
    error: resultsError,
    refetch: refetchResults,
  } = useQuery({
    queryKey: ['evaluation-results', id],
    queryFn: () => evaluationApi.getEvaluationResults(id!),
    enabled: !!id && isTerminal,
    retry: 2,
    staleTime: 5000,
    refetchInterval: (query) => (isTerminal && !query.state.data ? 1500 : false),
  });

  const isPartial = Boolean(results?.is_partial || evaluation?.partial_without_curriculum);
  const partialReason = results?.partial_reason || evaluation?.partial_reason;

  const agentLabels: Record<string, string> = useMemo(
    () => ({
      sme: 'Subject Matter Expert (SME)',
      coordinator: 'Program Coordinator',
      gad: 'Gender and Development (GAD)',
      itso: 'Innovation and IP (ITSO)',
    }),
    [],
  );

  const domainKeys = useMemo(() => {
    const canonical = ['sme', 'coordinator', 'gad', 'itso'];
    if (!results?.domain_scores) return canonical;
    const extras = Object.keys(results.domain_scores).filter((key) => !canonical.includes(key));
    return [...canonical, ...extras];
  }, [results]);

  if (!id) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-text-muted">
        No evaluation ID provided.
      </div>
    );
  }

  if (isLoading) {
    return <ScorecardSkeleton />;
  }

  if (isError || !evaluation) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-canvas">
        <div className="flex flex-col items-center gap-3 text-destructive border border-destructive/30 bg-destructive-soft p-8 rounded-md max-w-md text-center">
          <WarningCircle className="size-8 text-destructive" aria-hidden="true" />
          <p className="text-sm font-bold">Failed to load evaluation details.</p>
        </div>
      </div>
    );
  }

  const singleAgentMeta = isTargetAgent(evaluation.target_agent)
    ? TARGET_AGENT_META[evaluation.target_agent]
    : null;
  const isSingleAgentRun = singleAgentMeta !== null;

  // Active domain data on the right (auto-falls back to target agent or first available domain with scores)
  const targetAgentKey = isTargetAgent(evaluation.target_agent) ? evaluation.target_agent : null;
  const availableDomains = domainKeys.filter((k) => results?.domain_scores[k] != null);
  const effectiveDomainId = targetAgentKey && results?.domain_scores[targetAgentKey] != null
    ? targetAgentKey
    : availableDomains.includes(selectedDomainId)
      ? selectedDomainId
      : availableDomains[0] || domainKeys[0] || 'sme';
  const activeDomainData = results?.domain_scores[effectiveDomainId];
  const ActiveDomainIcon = DOMAIN_ICONS[effectiveDomainId] || FileText;

  const sortedCriteria = (activeDomainData?.criteria || []).slice().sort((a, b) => {
    if (a.display_order != null && b.display_order != null) {
      return a.display_order - b.display_order;
    }
    return a.criterion_id.localeCompare(b.criterion_id, undefined, { numeric: true });
  });
  return (
    <section className="flex h-[calc(100vh-4rem)] min-h-0 flex-col bg-canvas">
      {/* Top Dossier Context Header */}
      <header className="flex min-h-14 shrink-0 flex-wrap items-center justify-between gap-4 border-b border-border bg-surface px-4 sm:px-6">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted select-none">
            QA Scorecard
          </span>
          <span className="text-border">|</span>
          <h1 className="text-sm font-bold text-text truncate max-w-md" title={results?.document_title || evaluation.document_id}>
            {results?.document_title || evaluation.document_id}
          </h1>
          {isTargetAgent(evaluation.target_agent) ? (
            <Badge variant="info">
              {TARGET_AGENT_META[evaluation.target_agent].shortLabel} Evaluation
            </Badge>
          ) : isPartial ? (
            <Badge variant="warning" withDot>
              Partial Review
            </Badge>
          ) : null}
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {isSingleAgentRun && isTargetAgent(evaluation.target_agent) && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setShowReevaluateModal(true)}
              className="text-xs h-8 px-3 font-semibold gap-1.5"
            >
              <ArrowsClockwise className="size-3.5" aria-hidden="true" />
              <span>Re-evaluate</span>
            </Button>
          )}
          {results && activeDomainData && (
            <SpecialistExportDownloadButton
              domainData={{
                agentId: effectiveDomainId,
                documentTitle: results.document_title || evaluation.document_id,
                program: results.program ?? null,
                evaluationId: evaluation.evaluation_id,
                isPartial: results.is_partial,
                partialReason: results.partial_reason,
                evaluationStatus: results.evaluation_status,
                subtotal: activeDomainData.subtotal,
                max_score: activeDomainData.max_score || 4,
                status: activeDomainData.status,
                adjectival_rating: activeDomainData.adjectival_rating ?? undefined,
                criteria: activeDomainData.criteria || [],
                summary: activeDomainData.summary,
                version: activeDomainData.version,
                form_snapshot_id: activeDomainData.form_snapshot_id,
                results,
              }}
            />
          )}
          {!isSingleAgentRun && results && isTerminal ? (
            <ScorecardPdfExport results={results} />
          ) : null}
        </div>
      </header>

      {isSingleAgentRun && singleAgentMeta ? (
        /* Full-Width Single-Domain Specialist Dossier */
        <main
          aria-label="Specialist Evaluation Dossier"
          className="flex-1 overflow-y-auto bg-canvas p-4 sm:p-6 md:p-8 max-w-[80rem] w-full mx-auto space-y-6"
        >
          {isEvaluating ? (
            <div className="rounded-md border border-info/30 bg-info-soft/20 p-12 text-center flex flex-col items-center justify-center space-y-4 shadow-none">
              <div className="flex size-12 items-center justify-center rounded-sm bg-info/10 text-info border border-info/20">
                <Spinner className="size-6 text-info animate-spin" aria-hidden="true" />
              </div>
              <div className="space-y-1.5 max-w-md">
                <h2 className="text-base font-bold text-text">
                  {singleAgentMeta.fullName} Evaluation in Progress
                </h2>
                <p className="text-xs text-text-muted leading-relaxed">
                  Analyzing learning module content and grounding criteria against institutional quality standards. Status: <strong className="font-semibold text-text uppercase">{evaluation.status}</strong>.
                </p>
                <p className="text-[11px] text-text-muted">
                  Results typically arrive within 20–30 seconds. This page updates automatically.
                </p>
              </div>
            </div>
          ) : isFailed ? (
            <div className="rounded-md border border-destructive/30 bg-destructive-soft p-8 text-center space-y-2">
              <WarningCircle className="size-6 text-destructive mx-auto" aria-hidden="true" />
              <h2 className="text-sm font-bold text-destructive">Evaluation Failed</h2>
              <p className="text-xs text-text-muted max-w-md mx-auto">
                {evaluation.error_message || 'The evaluation job failed to complete. Please try submitting again.'}
              </p>
            </div>
          ) : isLoadingResults ? (
            <div className="rounded-md border border-border bg-surface p-12 text-center flex flex-col items-center justify-center space-y-3">
              <Spinner className="size-6 text-primary animate-spin" aria-hidden="true" />
              <p className="text-xs text-text-muted">Loading evaluation score breakdown…</p>
            </div>
          ) : activeDomainData ? (
            <div className="space-y-6">
              {/* Scorecard Hero Summary Card */}
              <div className="rounded-md border border-border bg-surface p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-none">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
                      {singleAgentMeta.fullName} Review
                    </span>
                    {activeDomainData.version != null ? (
                      <Badge variant="neutral">Revision {activeDomainData.version}</Badge>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-2xl font-bold text-text tabular-nums">
                      {formatScore(activeDomainData.subtotal)} / {formatScore(activeDomainData.max_score || 4)}
                    </span>
                    {activeDomainData.adjectival_rating ? (
                      <span
                        className={cn(
                          'inline-flex items-center rounded-xs px-2.5 py-1 text-xs font-bold uppercase tracking-wider',
                          getAdjectivalRatingClasses(activeDomainData.adjectival_rating),
                        )}
                      >
                        {activeDomainData.adjectival_rating}
                      </span>
                    ) : null}
                    <span className="text-xs text-text-muted tabular-nums font-semibold">
                      ({monitoringPercentage(activeDomainData.subtotal, activeDomainData.max_score || 4)}% Accreditation Compliance)
                    </span>
                  </div>
                  <p className="text-xs text-text-muted mt-1 leading-relaxed max-w-2xl">
                    {activeDomainData.summary || singleAgentMeta.requirement}
                  </p>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setReviewModalAgent(effectiveDomainId)}
                    className="text-xs h-8 px-3 font-semibold"
                  >
                    <span>Review & Correct Scores</span>
                  </Button>
                </div>
              </div>

              {/* Criteria & Verbatim Evidence Table */}
              <div className="rounded-md border border-border bg-surface overflow-hidden shadow-none">
                <div className="border-b border-border bg-surface-subtle px-5 py-3 flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-text">
                    Criteria Breakdown ({sortedCriteria.length} Criteria)
                  </span>
                  <span className="text-[11px] text-text-muted tabular-nums">
                    Submitted: {new Date(evaluation.submitted_at).toLocaleDateString()}
                    {evaluation.completed_at ? ` · Completed: ${new Date(evaluation.completed_at).toLocaleDateString()}` : ''}
                  </span>
                </div>

                <div className="divide-y divide-border bg-surface">
                  {sortedCriteria.map((criterion, idx) => {
                    const isUngrounded = Boolean(criterion.is_ungrounded);
                    const isPassing = criterion.score >= 3.0;

                    return (
                      <div
                        key={`${effectiveDomainId}-${criterion.criterion_id || idx}`}
                        className="p-4 sm:p-6 space-y-3 hover:bg-surface-subtle/30 transition-colors"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="flex items-start gap-2.5 min-w-0 flex-1">
                            <span className="font-mono text-xs font-bold text-primary shrink-0 whitespace-nowrap bg-primary-soft/50 border border-primary/20 px-1.5 py-0.5 rounded-xs mt-0.5">
                              {criterion.criterion_id}
                            </span>
                            <div className="min-w-0">
                              <span className="font-bold text-text text-sm block leading-snug">
                                {criterion.criterion_text}
                              </span>
                              {criterion.description ? (
                                <p className="text-xs text-text-muted mt-1 leading-relaxed">
                                  {criterion.description}
                                </p>
                              ) : null}
                            </div>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            {isUngrounded ? (
                              <Badge variant="warning">Ungrounded</Badge>
                            ) : null}
                            <span
                              className={cn(
                                'inline-flex items-center rounded-xs px-2.5 py-0.5 text-xs font-bold tabular-nums border',
                                isPassing
                                  ? 'bg-success-soft text-success border-success/30'
                                  : 'bg-warning-soft text-warning border-warning/30',
                              )}
                            >
                              Score {formatScore(criterion.score)} / 4
                            </span>
                          </div>
                        </div>

                        {/* Quoted Evidence & Findings Callout */}
                        {criterion.justification || criterion.evidence ? (
                          <div className="rounded-sm border border-border bg-surface-subtle p-3.5 space-y-2 text-xs">
                            {criterion.evidence ? (
                              <div className="space-y-1">
                                <span className="font-bold text-[10px] uppercase tracking-wider text-text-muted block">
                                  Quoted SLM Evidence
                                </span>
                                <blockquote className="border-l-2 border-primary/40 pl-2.5 font-mono text-[11px] text-text leading-relaxed">
                                  &ldquo;{criterion.evidence}&rdquo;
                                </blockquote>
                              </div>
                            ) : null}
                            {criterion.justification ? (
                              <div className="space-y-1">
                                <span className="font-bold text-[10px] uppercase tracking-wider text-text-muted block">
                                  Specialist Finding
                                </span>
                                <p className="text-text-muted leading-relaxed font-sans">
                                  {cleanJustification(criterion.justification)}
                                </p>
                              </div>
                            ) : null}
                          </div>
                        ) : null}

                        {/* Reviewer Correction Callout if Present */}
                        {criterion.reviewer_correction ? (
                          <div className="rounded-sm border border-info/30 bg-info-soft/20 p-3 text-xs space-y-1">
                            <span className="font-bold text-info block text-[10px] uppercase">
                              {criterion.reviewer_correction.action === 'REJECT'
                                ? 'Authoritative CID Human Override Flagged (Rejected)'
                                : 'Authoritative CID Human Override Applied'}
                            </span>
                            {criterion.reviewer_correction.score != null ? (
                              <p className="text-text font-medium">
                                Override Score: {criterion.reviewer_correction.score} / 4
                              </p>
                            ) : null}
                            {criterion.reviewer_correction.justification ? (
                              <p className="text-text-muted leading-relaxed">
                                <strong>Reviewer Justification: </strong>
                                {cleanJustification(criterion.reviewer_correction.justification)}
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Authoritative Human Review & Sign-Off */}
              <div className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-3 shadow-none">
                <div className="border-b border-border pb-2.5">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-text">
                    Authoritative Faculty Review & Sign-Off
                  </h3>
                  <p className="text-xs text-text-muted mt-0.5">
                    Automated evaluation findings are advisory. CID faculty evaluators maintain final authoritative determination.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-2 text-xs">
                  <div className="border-t border-border pt-1.5 text-text font-medium">
                    CID Evaluator / Reviewer Signature
                  </div>
                  <div className="border-t border-border pt-1.5 text-text font-medium">
                    Date Completed & Verified
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-md border border-border bg-surface p-8 text-center text-text-muted text-xs">
              No criteria recorded for this evaluation.
            </div>
          )}
        </main>
      ) : (
        /* 2-Column Side-by-Side Assessment Workspace (Historical 4-Agent Bundles) */
        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[22rem_minmax(0,1fr)] xl:grid-cols-[26rem_minmax(0,1fr)]">
        <aside
          aria-label="Executive Dossier & Review Domains"
          className="flex flex-col h-full min-h-0 border-r border-border bg-surface overflow-y-auto p-4 sm:p-5 space-y-4"
        >
          {/* Overall Verdict Card */}
          {results ? (
            availableDomains.length < 4 && isTargetAgent(evaluation.target_agent) ? (
              <div className="rounded-md border border-border bg-surface-subtle p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
                    Accreditation Progress
                  </span>
                  <Badge variant="info">In Progress</Badge>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-text tabular-nums">
                    {availableDomains.length} / 4 Domains Evaluated
                  </span>
                </div>
                <span className="text-[11px] text-text-muted block">
                  Composite score finalizes once all 4 specialist domains are evaluated.
                </span>
              </div>
            ) : (
              (() => {
                const display = overallScoreDisplay({
                  overallScore: results.overall_score,
                  synthesizedScore: results.synthesized_score,
                });
                return (
                  <div className="rounded-md border border-border bg-surface-subtle p-4 space-y-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
                      Overall Assessment Verdict
                    </span>
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          'inline-flex items-center rounded-xs px-2.5 py-1 text-xs font-bold uppercase tracking-wider',
                          getAdjectivalRatingClasses(results.adjectival_rating ?? undefined),
                        )}
                      >
                        {results.adjectival_rating}
                      </span>
                      <span className="text-sm font-bold text-text tabular-nums">
                        ★ {display.canonicalText}
                      </span>
                    </div>
                    <span className="text-[11px] text-text-muted tabular-nums block">
                      {display.monitoringText} monitoring percentage
                    </span>
                  </div>
                );
              })()
            )
          ) : null}

          {/* Legacy notice */}
          {results?.legacy_notice && (
            <div className="rounded-sm border border-border bg-surface-subtle p-3 text-xs text-text-muted leading-relaxed font-medium">
              {results.legacy_notice}
            </div>
          )}

          {/* Partial Notice */}
          {isPartial && !isTargetAgent(evaluation.target_agent) && (
            <div className="rounded-sm border border-warning/30 bg-warning-soft p-3 text-xs text-warning leading-relaxed">
              <strong>Partial Review: </strong>
              {partialReason ||
                'This evaluation ran without a curriculum reference. Coordinator review was skipped.'}
            </div>
          )}

          {/* 4-Domain Navigation Matrix */}
          <div className="space-y-2 pt-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted block px-1">
              Review Domains ({domainKeys.length})
            </span>

            <div className="space-y-1.5" role="tablist" aria-label="Review domain selection">
              {domainKeys.map((domain) => {
                const Icon = DOMAIN_ICONS[domain] || FileText;
                const domainData = results?.domain_scores[domain];
                const isSkipped = isPartial && domain === 'coordinator' && !domainData;
                const isSelected = domain === effectiveDomainId;
                const percent = domainData ? monitoringPercentage(domainData.subtotal, domainData.max_score || 4) : 0;

                if (isSkipped) {
                  return (
                    <div
                      key={`${domain}-nav-skipped`}
                      className="rounded-sm border border-border bg-surface-subtle/50 p-3 flex items-center justify-between text-xs opacity-70"
                    >
                      <div className="flex items-center gap-2">
                        <Icon className="size-4 text-text-muted" aria-hidden="true" />
                        <span className="font-semibold text-text-muted">
                          {agentLabels[domain]?.split(' ')[0] || domain}
                        </span>
                      </div>
                      <Badge variant="warning">Skipped</Badge>
                    </div>
                  );
                }

                if (!domainData) {
                  return (
                    <div
                      key={`${domain}-nav-pending`}
                      className="rounded-sm border border-dashed border-border bg-surface-subtle/30 p-3 flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="flex size-7 items-center justify-center rounded-xs shrink-0 bg-surface text-text-muted border border-border">
                          <Icon className="size-4" aria-hidden="true" />
                        </div>
                        <div className="min-w-0">
                          <span className="font-semibold text-text-muted block truncate">
                            {agentLabels[domain]?.split(' ')[0] || domain}
                          </span>
                          <span className="text-[10px] text-text-muted font-mono">Not evaluated</span>
                        </div>
                      </div>
                      <Badge variant="neutral">Pending</Badge>
                    </div>
                  );
                }
                return (
                  <button
                    key={domain}
                    type="button"
                    role="tab"
                    aria-selected={isSelected}
                    onClick={() => setSelectedDomainId(domain)}
                    className={cn(
                      'w-full text-left p-3 rounded-sm border transition-all flex items-start justify-between gap-3 cursor-pointer select-none',
                      isSelected
                        ? 'border-primary bg-primary-soft/50 text-primary shadow-xs ring-1 ring-primary/20'
                        : 'border-border bg-surface hover:bg-surface-subtle hover:border-border-strong text-text',
                    )}
                  >
                    <div className="flex items-start gap-2.5 min-w-0">
                      <div
                        className={cn(
                          'flex size-7 items-center justify-center rounded-xs shrink-0 mt-0.5 border',
                          isSelected
                            ? 'bg-primary-soft text-primary border-primary/30'
                            : 'bg-surface-subtle text-text-muted border-border',
                        )}
                      >
                        <Icon className="size-4" aria-hidden="true" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-xs truncate">
                            {agentLabels[domain]?.split(' ')[0] || domain}
                          </span>
                          {domainData.version != null ? (
                            <Badge variant="neutral">Rev {domainData.version}</Badge>
                          ) : null}
                        </div>
                        <span className="text-[11px] text-text-muted block mt-0.5 tabular-nums">
                          {formatScore(domainData.subtotal)} / {formatScore(domainData.max_score || 4)} ({percent}%)
                        </span>
                      </div>
                    </div>

                    <CaretRight
                      className={cn(
                        'size-4 shrink-0 transition-transform mt-1.5',
                        isSelected ? 'text-primary' : 'text-text-muted',
                      )}
                    />
                  </button>
                );
              })}
            </div>
          </div>

          {/* Audit Timing & Metadata */}
          <div className="border-t border-border pt-3 space-y-1.5 text-[11px] text-text-muted font-medium">
            <div className="flex items-center justify-between">
              <span>Submitted:</span>
              <strong className="text-text tabular-nums">{new Date(evaluation.submitted_at).toLocaleDateString()}</strong>
            </div>
            {evaluation.completed_at ? (
              <div className="flex items-center justify-between">
                <span>Completed:</span>
                <strong className="text-text tabular-nums">{new Date(evaluation.completed_at).toLocaleDateString()}</strong>
              </div>
            ) : null}
            {results?.duration_seconds != null ? (
              <div className="flex items-center justify-between">
                <span>Duration:</span>
                <strong className="text-text tabular-nums">{formatDuration(results.duration_seconds)}</strong>
              </div>
            ) : null}
          </div>
        </aside>

        {/* RIGHT COLUMN: Active Domain Criteria & Quoted Evidence (~62% width) */}
        <main
          aria-label="Domain Criteria & Findings"
          className="flex flex-col h-full min-h-0 overflow-y-auto bg-canvas p-4 sm:p-6 md:p-8 space-y-5"
        >
          {isEvaluating ? (
            <div className="rounded-md border border-info/30 bg-info-soft/20 p-12 text-center flex flex-col items-center justify-center space-y-4 shadow-none">
              <div className="flex size-12 items-center justify-center rounded-sm bg-info/10 text-info border border-info/20">
                <Spinner className="size-6 text-info animate-spin" aria-hidden="true" />
              </div>
              <div className="space-y-1.5 max-w-md">
                <h2 className="text-base font-bold text-text">
                  Multi-Agent Evaluation in Progress
                </h2>
                <p className="text-xs text-text-muted leading-relaxed">
                  Specialist agents are evaluating module content against institutional quality standards. Status: <strong className="font-semibold text-text uppercase">{evaluation.status}</strong>.
                </p>
                <p className="text-[11px] text-text-muted">
                  Results will populate automatically upon completion.
                </p>
              </div>
            </div>
          ) : isFailed ? (
            <div className="rounded-md border border-destructive/30 bg-destructive-soft p-8 text-center space-y-2">
              <WarningCircle className="size-6 text-destructive mx-auto" aria-hidden="true" />
              <h2 className="text-sm font-bold text-destructive">Evaluation Failed</h2>
              <p className="text-xs text-text-muted max-w-md mx-auto">
                {evaluation.error_message || 'The evaluation job failed to complete.'}
              </p>
            </div>
          ) : activeDomainData ? (
            <div className="space-y-5">
              {/* Active Domain Header Bar */}
              <div className="rounded-md border border-border bg-surface p-5 sm:p-6 flex flex-wrap items-center justify-between gap-4 shadow-none">
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className="flex size-9 items-center justify-center rounded-xs bg-primary-soft text-primary border border-primary/20 shrink-0">
                    <ActiveDomainIcon className="size-5" aria-hidden="true" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className={TYPOGRAPHY.headingSm}>
                        {agentLabels[effectiveDomainId] || effectiveDomainId.toUpperCase()}
                      </h2>
                      {activeDomainData.version != null ? (
                        <Badge variant="neutral">Revision {activeDomainData.version}</Badge>
                      ) : null}
                      {activeDomainData.version == null &&
                        (results?.legacy_notice || activeDomainData.form_snapshot_id == null) &&
                        results && (
                          <Badge variant="neutral">Legacy — form snapshot unavailable</Badge>
                        )}
                    </div>
                    <p className="text-xs text-text-muted mt-0.5">
                      {activeDomainData.summary || 'Domain review criteria evaluated against institutional quality standards.'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs font-bold text-text tabular-nums">
                    Subtotal: {formatScore(activeDomainData.subtotal)} / {formatScore(activeDomainData.max_score || 4)}
                  </span>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setReviewModalAgent(effectiveDomainId)}
                    className="text-xs h-7.5 px-2.5"
                  >
                    Review Scores
                  </Button>
                </div>
              </div>

              {/* Criteria Table */}
              <div className="rounded-md border border-border bg-surface overflow-hidden shadow-none">
                <div className="divide-y divide-border bg-surface">
                  {sortedCriteria.map((criterion, idx) => {
                    const isUngrounded = Boolean(criterion.is_ungrounded);
                    const isPassing = criterion.score >= 3.0;

                    return (
                      <div
                        key={`${effectiveDomainId}-${criterion.criterion_id || idx}`}
                        className="p-4 sm:p-5 space-y-2.5 hover:bg-surface-subtle/30 transition-colors"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="flex items-start gap-2.5 min-w-0 flex-1">
                            <span className="font-mono text-xs font-bold text-text-muted shrink-0 whitespace-nowrap bg-surface-subtle border border-border px-1.5 py-0.5 rounded-xs mt-0.5">
                              {criterion.criterion_id}
                            </span>
                            <div className="min-w-0">
                              <span className="font-semibold text-text text-sm block leading-snug">
                                {criterion.criterion_text}
                              </span>
                              {criterion.description ? (
                                <p className="text-xs text-text-muted mt-1 leading-relaxed">
                                  {criterion.description}
                                </p>
                              ) : null}
                            </div>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            {isUngrounded ? (
                              <Badge variant="warning">Ungrounded</Badge>
                            ) : null}
                            <span
                              className={cn(
                                'inline-flex items-center rounded-xs px-2.5 py-0.5 text-xs font-bold tabular-nums border',
                                isPassing
                                  ? 'bg-success-soft text-success border-success/30'
                                  : 'bg-warning-soft text-warning border-warning/30',
                              )}
                            >
                              Score {formatScore(criterion.score)} / 4
                            </span>
                          </div>
                        </div>

                        {/* Quoted Evidence & Findings Callout */}
                        {criterion.justification || criterion.evidence ? (
                          <div className="rounded-sm border border-warning/30 bg-warning-soft/15 p-3.5 space-y-1.5 text-xs">
                            {criterion.evidence ? (
                              <div className="font-mono text-text bg-surface/80 p-2.5 border border-border rounded-xs">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block mb-0.5">
                                  Quoted Evidence:
                                </span>
                                "{cleanJustification(criterion.evidence)}"
                              </div>
                            ) : null}
                            {criterion.justification ? (
                              <p className="text-text-muted leading-relaxed">
                                <strong>Specialist Finding: </strong>
                                {cleanJustification(criterion.justification)}
                              </p>
                            ) : null}
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 text-xs text-success font-medium pt-0.5">
                            <CheckCircle className="size-3.5 text-success shrink-0" aria-hidden="true" />
                            <span>Verified compliant with institutional quality standards.</span>
                          </div>
                        )}
                        {/* Reviewer Correction Callout if Present */}
                        {criterion.reviewer_correction ? (
                          <div className="rounded-sm border border-info/30 bg-info-soft/20 p-3 text-xs space-y-1">
                            <span className="font-bold text-info block text-[10px] uppercase">
                              {criterion.reviewer_correction.action === 'REJECT'
                                ? 'Authoritative CID Human Override Flagged (Rejected)'
                                : 'Authoritative CID Human Override Applied'}
                            </span>
                            {criterion.reviewer_correction.score != null ? (
                              <p className="text-text font-medium">
                                Override Score: {criterion.reviewer_correction.score} / 4
                              </p>
                            ) : null}
                            {criterion.reviewer_correction.justification ? (
                              <p className="text-text-muted leading-relaxed">
                                <strong>Reviewer Justification: </strong>
                                {cleanJustification(criterion.reviewer_correction.justification)}
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Authoritative Human Review & Sign-Off */}
              <div className="rounded-md border border-border bg-surface p-5 sm:p-6 space-y-3">
                <div className="border-b border-border pb-2.5">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-text">
                    Authoritative Faculty Review & Sign-Off
                  </h3>
                  <p className="text-xs text-text-muted mt-0.5">
                    Automated multi-agent evaluation findings are advisory. CID faculty evaluators maintain final authoritative determination.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-2 text-xs">
                  <div className="border-t border-border pt-1.5 text-text font-medium">
                    CID Evaluator / Reviewer Signature
                  </div>
                  <div className="border-t border-border pt-1.5 text-text font-medium">
                    Date Completed & Verified
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-full min-h-[20rem] items-center justify-center p-8 text-center text-text-muted">
              Select a domain on the left to inspect criteria.
            </div>
          )}
        </main>
        </div>
      )}
      {/* Review Scores Modal */}
      {reviewModalAgent && id && (
        <AgentReviewModal
          agentName={reviewModalAgent}
          evaluationId={id}
          criteria={results?.domain_scores[reviewModalAgent]?.criteria || []}
          onClose={() => setReviewModalAgent(null)}
        />
      )}
      {/* Re-evaluate Confirmation Modal */}
      {showReevaluateModal && isTargetAgent(evaluation.target_agent) && (
        <EvaluationConfirmModal
          documentId={evaluation.document_id}
          documentTitle={results?.document_title || evaluation.document_id}
          detectedProgram={results?.program ?? null}
          targetAgent={evaluation.target_agent}
          onClose={() => setShowReevaluateModal(false)}
          onSubmitted={(newEvaluationId) => {
            setShowReevaluateModal(false);
            void queryClient.invalidateQueries({ queryKey: ['evaluation'] });
            void queryClient.invalidateQueries({ queryKey: ['evaluation-results'] });
            void queryClient.invalidateQueries({ queryKey: ['evaluation-history'] });
            void navigate({
              to: '/evaluations/$id',
              params: { id: newEvaluationId },
            });
          }}
        />
      )}
    </section>
  );
}
