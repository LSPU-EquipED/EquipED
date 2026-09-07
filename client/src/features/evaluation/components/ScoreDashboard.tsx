import { Fragment, useState } from 'react';
import {
  BookOpen,
  CaretDown,
  CaretUp,
  ChatTeardropText,
  CheckCircle,
  Circle,
  Clock,
  Eye,
  Lightbulb,
  Quotes,
  Scales,
  Spinner,
  Target,
  WarningCircle,
  XCircle,
} from '@phosphor-icons/react';
import { useNavigate } from '@tanstack/react-router';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { TABLE_STYLES, TYPOGRAPHY } from '@/shared/constants/theme';
import {
  formatScore,
  agentShortLabel,
  cleanJustification,
} from '../utils/scoreHelpers';
import type {
  CriterionScoreItem,
  EvaluationResultsResponse,
  EvaluationStatusResponse,
} from '../types';

const agents = [
  {
    id: 'coordinator',
    name: 'Program Coordinator',
    subtitle: 'Curriculum alignment',
    icon: BookOpen,
  },
  {
    id: 'sme',
    name: 'Subject Matter Expert (SME)',
    subtitle: 'Discipline accuracy',
    icon: Lightbulb,
  },
  {
    id: 'gad',
    name: 'GAD Unit',
    subtitle: 'Gender and development review',
    icon: Scales,
  },
  {
    id: 'itso',
    name: 'ITSO',
    subtitle: 'Intellectual property & citations',
    icon: Target,
  },
] as const;

type AgentId = (typeof agents)[number]['id'];

const PIPELINE_STAGES = [
  { key: 'SUBMITTED', label: 'Queued' },
  { key: 'PREPROCESSING', label: 'Preprocessing' },
  { key: 'EVALUATING', label: 'Evaluation' },
  { key: 'SYNTHESIZING', label: 'Synthesis' },
  { key: 'COMPLETED', label: 'Completed' },
] as const;

function getStageIndex(status?: string): number {
  if (!status) return 0;
  const index = PIPELINE_STAGES.findIndex((s) => s.key === status);
  return index >= 0 ? index : 0;
}

function getAdjectivalRatingClasses(rating?: string | null): string {
  switch (rating) {
    case 'VERY SATISFACTORY':
    case 'OUTSTANDING':
      return 'bg-success-soft text-success border border-success/25';
    case 'SATISFACTORY':
      return 'bg-info-soft text-info border border-info/25';
    case 'UNSATISFACTORY':
    case 'POOR':
      return 'bg-destructive-soft text-destructive border border-destructive/25';
    default:
      return 'bg-warning-soft text-warning border border-warning/25';
  }
}

function getScoreRatingClasses(score: number): string {
  if (score >= 3) {
    return 'border-success/30 bg-success-soft/40 text-success';
  }
  if (score === 2) {
    return 'border-border bg-surface-subtle text-text';
  }
  return 'border-warning/40 bg-warning-soft/40 text-warning';
}

function getAgentCardState(
  agentId: string,
  results?: EvaluationResultsResponse,
  isPartial?: boolean,
): 'done' | 'running' | 'failed' | 'pending' | 'skipped' {
  if (!results) return 'pending';
  if (isPartial && agentId === 'coordinator') return 'skipped';
  if (results.active_agents.includes(agentId)) return 'done';
  if (results.failed_agents.includes(agentId)) return 'failed';
  return 'running';
}

function formatDuration(seconds?: number | null): string {
  if (seconds == null) return '';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

function getShortStatusLabel(score: number): string {
  if (score >= 3) return 'Strong';
  if (score >= 2) return 'Moderate';
  return 'Needs attention';
}

type ScoreDashboardProps = {
  status: EvaluationStatusResponse | undefined;
  results: EvaluationResultsResponse | undefined;
  isTerminal: boolean;
  isInProgress: boolean;
  isFailedWithResults: boolean;
  isResultsError: boolean;
  resultsError: unknown;
  refetchResults: () => void;
  handleRetryEvaluation: () => void;
  isResolvingEval: boolean;
  submitIsPending: boolean;
  evaluationId: string | null | undefined;
  selectedAgentId: AgentId;
  onSelectAgent: (id: AgentId) => void;
};

export function ScoreDashboard({
  status,
  results,
  isTerminal,
  isInProgress,
  isFailedWithResults,
  isResultsError,
  resultsError: _resultsError,
  refetchResults: _refetchResults,
  handleRetryEvaluation,
  isResolvingEval,
  submitIsPending,
  evaluationId,
  selectedAgentId,
  onSelectAgent,
}: ScoreDashboardProps) {
  const navigate = useNavigate();

  // Option A: Manual toggle state for criteria rows keyed by agent (no cascading render effect)
  const [toggledCriteriaByAgent, setToggledCriteriaByAgent] = useState<
    Record<string, Record<string, boolean>>
  >({});
  const manuallyToggled = toggledCriteriaByAgent[selectedAgentId] ?? {};
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0];
  const domainScore = results?.domain_scores[selectedAgentId];
  const isPartial = Boolean(results?.is_partial || status?.partial_without_curriculum);
  const partialReason = results?.partial_reason || status?.partial_reason;

  // Sorted criteria list by display_order or natural numeric code sequence
  const sortedCriteria = (domainScore?.criteria ?? []).slice().sort((a, b) => {
    if (a.display_order != null && b.display_order != null) {
      return a.display_order - b.display_order;
    }
    return a.criterion_id.localeCompare(b.criterion_id, undefined, { numeric: true });
  });

  const selectedScore = {
    score: domainScore
      ? Math.round((domainScore.subtotal / (domainScore.max_score || 1)) * 100)
      : 0,
    rawScore: domainScore?.subtotal ?? 0,
    verdict: domainScore
      ? domainScore.status === 'OK'
        ? 'Acceptable'
        : domainScore.status === 'ERROR'
          ? 'Failed'
          : 'Review recommended'
      : isInProgress
        ? 'Evaluating…'
        : '—',
    summary: domainScore
      ? domainScore.summary
      : isInProgress
        ? 'Evaluation in progress...'
        : isPartial && selectedAgent.id === 'coordinator'
          ? 'Program Coordinator review was skipped because this evaluation ran without a curriculum reference.'
          : isFailedWithResults
            ? 'Evaluation failed, but partial results are available.'
            : 'Evaluation results are not available yet.',
    feedbackCriteria: sortedCriteria,
    rows: sortedCriteria.map((criterion: CriterionScoreItem) => ({
      rating: formatScore(criterion.score),
      code: criterion.criterion_id,
      criterion: criterion.criterion_text,
      description: criterion.description,
      status: criterion.is_ungrounded ? 'Ungrounded' : getShortStatusLabel(criterion.score),
      isUngrounded: Boolean(criterion.is_ungrounded),
    })),
  };

  // Option A (Smart Default): Automatically expand if score <= 2, has flags, or is ungrounded
  const isCriterionExpanded = (
    criterionId: string,
    score: number,
    hasFlags: boolean,
    isUngrounded: boolean,
  ): boolean => {
    if (manuallyToggled[criterionId] !== undefined) {
      return manuallyToggled[criterionId];
    }
    return score <= 2 || hasFlags || isUngrounded;
  };

  const toggleCriterion = (criterionId: string, currentState: boolean) => {
    setToggledCriteriaByAgent((prev) => ({
      ...prev,
      [selectedAgentId]: {
        ...(prev[selectedAgentId] ?? {}),
        [criterionId]: !currentState,
      },
    }));
  };

  const handleViewFullReport = () => {
    if (evaluationId) {
      void navigate({ to: '/evaluations/$id', params: { id: evaluationId } });
    }
  };

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-canvas">
      {/* Streamlined Synthesis Top Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface px-5 sm:px-6 py-3 shrink-0">
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-bold uppercase tracking-wider text-text">
            Evaluation Synthesis
          </span>
          <span className="text-text-muted/60 text-xs font-mono">·</span>
          <span className="text-xs text-text-muted">Advisory Specialist Review</span>
          {isPartial && (
            <Badge variant="warning" withDot>
              Partial Review
            </Badge>
          )}
        </div>

        {/* Overall Score Badge */}
        {results?.adjectival_rating ? (
          <div className="flex items-center gap-2.5 shrink-0">
            <span
              className={cn(
                'inline-flex items-center rounded-xs px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider',
                getAdjectivalRatingClasses(results.adjectival_rating),
              )}
            >
              {results.adjectival_rating}
            </span>
            {typeof results.overall_score === 'number' ? (
              <span className="text-xs font-bold tabular-nums text-text bg-surface-subtle px-2 py-0.5 rounded-xs border border-border">
                ★ {formatScore(results.overall_score)} / 4.0
              </span>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* Main Body */}
      <div className="p-4 sm:p-5 space-y-4 flex-1">
        {/* Pipeline Stage Bar (when running) */}
        {evaluationId && !isTerminal && (
          <div className="rounded-md border border-border bg-surface p-4">
            <div className="flex items-center gap-1">
              {PIPELINE_STAGES.map((stage, index) => {
                const currentIndex = getStageIndex(status?.status);
                const isFailed = status?.status === 'FAILED';
                const isCompleted =
                  !isFailed &&
                  (index < currentIndex ||
                    (status?.status === 'COMPLETED' && index === currentIndex));
                const isCurrent =
                  !isFailed && index === currentIndex && status?.status !== 'COMPLETED';
                const isUpcoming = isFailed || index > currentIndex;

                return (
                  <div key={stage.key} className="flex flex-1 items-center">
                    <div
                      className={cn(
                        'flex flex-1 flex-col items-center gap-1 py-1 rounded-sm',
                        isCurrent && 'bg-primary-soft/40',
                      )}
                    >
                      <span
                        className={cn(
                          'grid size-5 place-items-center rounded-full text-[10px] font-bold',
                          isCompleted && 'bg-primary text-primary-foreground',
                          isCurrent && 'border-2 border-primary text-primary',
                          isUpcoming && 'border border-border text-text-muted',
                        )}
                      >
                        {isCompleted && <CheckCircle className="size-3" aria-hidden="true" />}
                        {isCurrent && (
                          <Spinner className="size-3 animate-spin" aria-hidden="true" />
                        )}
                        {isUpcoming && <Circle className="size-3" aria-hidden="true" />}
                      </span>
                      <span
                        className={cn(
                          'text-[9px] font-semibold uppercase tracking-wider',
                          isCompleted && 'text-primary',
                          isCurrent && 'text-primary font-bold',
                          isUpcoming && 'text-text-muted',
                        )}
                      >
                        {stage.label}
                      </span>
                    </div>
                    {index < PIPELINE_STAGES.length - 1 && (
                      <div
                        className={cn(
                          'h-0.5 flex-1 transition-colors',
                          index < currentIndex ? 'bg-primary' : 'bg-border',
                        )}
                      />
                    )}
                  </div>
                );
              })}
            </div>

            <div className="mt-3 flex items-center justify-between text-xs text-text-muted pt-2 border-t border-border">
              <span>{status?.status || 'Processing evaluation…'}</span>
              {isTerminal &&
                (results?.duration_seconds != null || status?.duration_seconds != null) && (
                  <span className="inline-flex items-center gap-1 font-mono text-[11px] tabular-nums">
                    <Clock className="size-3" aria-hidden="true" />
                    {formatDuration(results?.duration_seconds ?? status?.duration_seconds)}
                  </span>
                )}
            </div>
          </div>
        )}

        {/* Failed Banner */}
        {status?.status === 'FAILED' && (
          <div className="flex items-center justify-between gap-3 rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs text-destructive font-semibold" role="alert">
            <div className="flex items-center gap-2">
              <XCircle className="size-4 shrink-0" aria-hidden="true" />
              <span>
                {isFailedWithResults
                  ? 'Evaluation failed, but partial specialist findings are available below.'
                  : 'Evaluation failed. No results were produced.'}
              </span>
            </div>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={handleRetryEvaluation}
              disabled={isResolvingEval || submitIsPending}
            >
              Retry Evaluation
            </Button>
          </div>
        )}

        {/* Legacy notice */}
        {results?.legacy_notice && (
          <div className="rounded-sm border border-border bg-surface-subtle p-3 text-xs text-text-muted">
            {results.legacy_notice}
          </div>
        )}

        {/* Partial notice */}
        {isPartial && (
          <div className="rounded-sm border border-warning/30 bg-warning-soft p-3 text-xs text-warning leading-relaxed">
            <strong>Partial Evaluation: </strong>
            {partialReason ||
              'This evaluation ran without a curriculum reference. SME, GAD, and ITSO reviews are included, but Program Coordinator curriculum-grounded review was skipped.'}
          </div>
        )}

        {/* Perspective Domain Tabs Container */}
        <div className="rounded-md border border-border bg-surface overflow-hidden shadow-none">
          <div
            className="flex flex-wrap gap-1 border-b border-border bg-surface-subtle px-3 pt-2"
            role="tablist"
            aria-label="Select evaluation domain"
          >
            {agents.map((agent) => {
              const Icon = agent.icon;
              const isActive = agent.id === selectedAgentId;
              const agentState = getAgentCardState(agent.id, results, isPartial);

              return (
                <button
                  key={agent.name}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => onSelectAgent(agent.id)}
                  className={cn(
                    'flex items-center gap-2 rounded-t-sm px-3.5 py-2.5 text-xs font-semibold transition-colors cursor-pointer select-none border-b-2',
                    isActive
                      ? 'bg-surface text-primary border-primary font-bold shadow-none'
                      : 'border-transparent text-text-muted hover:text-text hover:bg-surface/50',
                  )}
                >
                  <Icon className="size-3.5" aria-hidden="true" />
                  <span>{agentShortLabel(agent.id)}</span>

                  {agentState !== 'pending' && (
                    <span
                      className={cn(
                        'ml-0.5 rounded-xs px-1.5 py-0.2 text-[9px] font-bold uppercase tracking-tight tabular-nums font-mono',
                        agentState === 'done' && 'bg-success-soft text-success border border-success/20',
                        agentState === 'running' && 'bg-primary-soft text-primary border border-primary/20',
                        agentState === 'failed' && 'bg-destructive-soft text-destructive border border-destructive/20',
                        agentState === 'skipped' && 'bg-warning-soft text-warning border border-warning/20',
                      )}
                    >
                      {agentState === 'done' && 'DONE'}
                      {agentState === 'running' && 'RUN'}
                      {agentState === 'skipped' && 'SKIP'}
                      {agentState === 'failed' && 'FAIL'}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Selected Domain Header */}
          <div className="p-4 sm:p-5 border-b border-border bg-surface">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-text">{selectedAgent.name}</h3>
                  {domainScore?.version != null ? (
                    <Badge variant="neutral" className="font-mono text-[11px]">
                      Revision {domainScore.version}
                    </Badge>
                  ) : null}
                  {domainScore?.version == null &&
                    (results?.legacy_notice || domainScore?.form_snapshot_id == null) &&
                    results && (
                      <Badge variant="neutral">Legacy — form snapshot unavailable</Badge>
                    )}
                </div>
                <p className="text-xs text-text-muted mt-1 leading-relaxed max-w-2xl font-normal">
                  {selectedScore.summary}
                </p>
              </div>

              {/* Monitoring Rating & Score */}
              {domainScore ? (
                <div className="flex items-center gap-2 shrink-0">
                  <Badge variant={selectedScore.score >= 70 ? 'success' : 'warning'}>
                    {selectedScore.score}% Monitoring Score
                  </Badge>
                </div>
              ) : null}
            </div>
          </div>

          {/* Ordered Criteria Table with Inline Expandable Findings (Option A) */}
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-16 text-center')}>
                    Score
                  </th>
                  <th scope="col" className={TABLE_STYLES.th}>
                    Evaluation Criterion
                  </th>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-36 text-right')}>
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className={TABLE_STYLES.tbody}>
                {selectedScore.rows.length > 0 ? (
                  selectedScore.rows.map((row) => {
                    const criterionItem = sortedCriteria.find((c) => c.criterion_id === row.code);
                    const criterionFlags = (results?.flags ?? []).filter(
                      (f) => f.agent_id === selectedAgentId && f.criterion_id === row.code,
                    );
                    const hasFlags = criterionFlags.length > 0;
                    const numScore = Number(row.rating);
                    const isExpanded = isCriterionExpanded(
                      row.code,
                      numScore,
                      hasFlags,
                      row.isUngrounded,
                    );

                    return (
                      <Fragment key={row.code}>
                        {/* Primary Criterion Row */}
                        <tr
                          className={cn(
                            TABLE_STYLES.tr,
                            'cursor-pointer transition-colors select-none',
                            isExpanded ? 'bg-surface-subtle/70' : 'hover:bg-surface-subtle/35',
                          )}
                          onClick={() => toggleCriterion(row.code, isExpanded)}
                        >
                          {/* Rating Number Badge with Status Heatmap */}
                          <td className="px-3.5 py-3 text-center align-top">
                            <span
                              className={cn(
                                'inline-flex size-7 items-center justify-center rounded-xs border text-xs font-bold tabular-nums',
                                getScoreRatingClasses(numScore),
                              )}
                            >
                              {row.rating}
                            </span>
                          </td>

                          {/* Criterion Description */}
                          <td className={TABLE_STYLES.td}>
                            <div className="flex flex-col space-y-1">
                              <div className="flex items-start gap-2.5">
                                <span className="font-mono text-xs font-bold text-text-muted shrink-0 whitespace-nowrap bg-surface-subtle border border-border px-1.5 py-0.5 rounded-xs mt-0.5">
                                  {row.code}
                                </span>
                                <span className="font-semibold text-text leading-snug flex-1 text-sm">
                                  {row.criterion}
                                </span>
                                {row.isUngrounded && (
                                  <Badge variant="warning" className="shrink-0">
                                    Ungrounded
                                  </Badge>
                                )}
                                {hasFlags && (
                                  <span className="inline-flex items-center gap-1 rounded-xs bg-warning-soft px-1.5 py-0.5 text-[10px] font-bold text-warning border border-warning/25 uppercase font-mono shrink-0">
                                    {criterionFlags.length}{' '}
                                    {criterionFlags.length === 1 ? 'Flag' : 'Flags'}
                                  </span>
                                )}
                                <button
                                  type="button"
                                  aria-label={
                                    isExpanded
                                      ? `Collapse details for ${row.code}`
                                      : `Expand details for ${row.code}`
                                  }
                                  className="ml-auto inline-flex size-6 shrink-0 items-center justify-center rounded-xs text-text-muted hover:text-text hover:bg-surface-subtle transition-colors"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleCriterion(row.code, isExpanded);
                                  }}
                                >
                                  {isExpanded ? (
                                    <CaretUp className="size-3.5" aria-hidden="true" />
                                  ) : (
                                    <CaretDown className="size-3.5" aria-hidden="true" />
                                  )}
                                </button>
                              </div>
                              {row.description && (
                                <p className="text-xs text-text-muted mt-0.5 leading-relaxed pl-0.5">
                                  {row.description}
                                </p>
                              )}
                            </div>
                          </td>

                          {/* Status */}
                          <td className={cn(TABLE_STYLES.td, 'text-right align-top')}>
                            <span
                              className={cn(
                                'text-xs font-semibold whitespace-nowrap',
                                row.isUngrounded
                                  ? 'text-warning'
                                  : numScore >= 3
                                    ? 'text-success'
                                    : 'text-warning',
                              )}
                            >
                              {row.status}
                            </span>
                          </td>
                        </tr>

                        {/* Inline Expandable Findings & Evidence Sub-Panel */}
                        {isExpanded && (
                          <tr className="bg-surface-subtle/40 border-b border-border">
                            <td colSpan={3} className="px-5 py-3.5">
                              <div className="space-y-2.5 max-w-4xl ml-10">
                                {/* Agent Assessment Rationale */}
                                {criterionItem?.justification && (
                                  <div className="rounded-sm border border-border/70 bg-surface p-3 space-y-1.5">
                                    <div className="flex items-center gap-1.5">
                                      <ChatTeardropText
                                        className="size-3.5 text-primary shrink-0"
                                        aria-hidden="true"
                                      />
                                      <span className="text-[10px] font-bold uppercase tracking-wider text-primary font-mono">
                                        Agent Assessment Rationale
                                      </span>
                                    </div>
                                    <p className="text-text leading-relaxed text-xs pl-5">
                                      {cleanJustification(criterionItem.justification)}
                                    </p>
                                  </div>
                                )}

                                {/* Quoted Module Evidence & Excerpts */}
                                {(criterionItem?.evidence || hasFlags) && (
                                  <div className="rounded-sm border border-border/70 bg-surface p-3 space-y-2">
                                    <div className="flex items-center gap-1.5">
                                      <Quotes
                                        className="size-3.5 text-primary shrink-0"
                                        aria-hidden="true"
                                      />
                                      <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted font-mono">
                                        Quoted Module Evidence & Citations
                                      </span>
                                    </div>
                                    <div className="space-y-1.5 pl-5">
                                      {criterionItem?.evidence && (
                                        <div className="rounded-xs border border-border bg-surface-subtle px-3 py-2 text-text-muted text-xs leading-relaxed italic">
                                          ❝ {criterionItem.evidence} ❞
                                        </div>
                                      )}
                                      {criterionFlags.map(
                                        (flag) =>
                                          flag.justification &&
                                          flag.justification !== criterionItem?.justification && (
                                            <div
                                              key={flag.flag_id}
                                              className="rounded-xs border border-warning/30 bg-warning-soft/20 px-3 py-2 text-xs text-text-muted leading-relaxed"
                                            >
                                              {cleanJustification(flag.justification)}
                                            </div>
                                          ),
                                      )}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={3} className="px-6 py-12 text-center text-xs text-text-muted">
                      {isInProgress
                        ? 'Criteria will appear once evaluation completes.'
                        : 'No criteria available for this domain.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>


        {/* Next Steps Card */}
        {isTerminal && evaluationId ? (
          <div className="rounded-md border border-border bg-surface p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-none">
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-text">
                Authoritative Human Review
              </h4>
              <p className="text-xs text-text-muted mt-0.5 max-w-xl">
                Automated evaluation findings are advisory. Open the full scorecard report to inspect individual agent rationales.
              </p>
            </div>

            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleViewFullReport}
              className="shrink-0"
            >
              <Eye className="size-3.5" aria-hidden="true" />
              <span>Open Full Report</span>
            </Button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
