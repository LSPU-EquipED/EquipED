import { Fragment } from 'react';
import {
  WarningCircle,
  BookOpen,
  CheckCircle,
  Circle,
  Clock,
  Eye,
  Spinner,
  Lightbulb,
  Scales,
  ShieldCheck,
  Target,
  XCircle,
} from '@phosphor-icons/react';
import { useNavigate } from '@tanstack/react-router';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES, TABLE_STYLES, TYPOGRAPHY } from '@/shared/constants/theme';
import { FeedbackPanel } from './FeedbackPanel';
import { formatScore, agentShortLabel, getCriterionCategory } from '../utils/scoreHelpers';
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
    subtitle: 'Innovation and compliance',
    icon: ShieldCheck,
  },
] as const;

type AgentId = (typeof agents)[number]['id'];

const PIPELINE_STAGES = [
  { key: 'SUBMITTED', label: 'Submitted' },
  { key: 'PREPROCESSING', label: 'Preprocessing' },
  { key: 'EVALUATING', label: 'Evaluating' },
  { key: 'SYNTHESIZING', label: 'Synthesizing' },
  { key: 'COMPLETED', label: 'Completed' },
] as const;

function getStageIndex(status: string | undefined): number {
  if (!status || status === 'FAILED') return -1;
  const idx = PIPELINE_STAGES.findIndex((s) => s.key === status);
  return idx >= 0 ? idx : -1;
}

function getAgentCardState(
  agentId: string,
  results:
    | { domain_scores: Record<string, unknown>; active_agents?: string[]; failed_agents?: string[] }
    | null
    | undefined,
  isPartial?: boolean,
): 'pending' | 'running' | 'done' | 'failed' | 'skipped' {
  if (!results) return 'pending';
  if (isPartial && agentId === 'coordinator') return 'skipped';
  if (results.failed_agents?.includes(agentId)) return 'failed';
  if (results.domain_scores[agentId]) return 'done';
  if (results.active_agents?.includes(agentId)) return 'running';
  return 'pending';
}

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

function getCriterionTier(rating: string): 'strong' | 'medium' | 'weak' | 'unknown' {
  const num = Number(rating);
  if (Number.isNaN(num)) return 'unknown';
  if (num >= 3) return 'strong';
  if (num >= 2) return 'medium';
  return 'weak';
}

function statusMessage(
  status: string | undefined,
  isFailedWithResults: boolean,
  isPartial: boolean,
): string {
  if (isFailedWithResults) {
    return 'Evaluation failed, but partial results are available for review.';
  }
  switch (status) {
    case 'SUBMITTED':
      return 'Job submitted. Waiting to start preprocessing…';
    case 'PREPROCESSING':
      return 'Preprocessing document contents and preparing chunks for evaluation…';
    case 'EVALUATING':
      return isPartial
        ? 'Running partial multi-agent evaluation. Coordinator review is skipped…'
        : 'Running multi-agent evaluation across all review domains…';
    case 'SYNTHESIZING':
      return 'Synthesizing agent reports and computing final scores…';
    case 'COMPLETED':
      return isPartial
        ? 'Partial evaluation completed. Coordinator/curriculum-grounded review was skipped.'
        : 'Evaluation completed. Review the scores and criteria below.';
    case 'FAILED':
      return 'Evaluation failed. No results were produced.';
    default:
      return 'Waiting for evaluation status…';
  }
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

  const handleViewFullReport = () => {
    if (evaluationId) {
      void navigate({ to: '/evaluations/$id', params: { id: evaluationId } });
    }
  };

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-canvas">
      {/* Streamlined Scorecard Top Summary Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border bg-surface px-6 py-3.5 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
              Advisory Evaluation Synthesis
            </span>
            {isPartial ? (
              <Badge variant="warning" withDot>
                Partial Review
              </Badge>
            ) : null}
          </div>
          <h2 className="text-lg font-bold text-text mt-0.5">Synthesized Agent View</h2>
        </div>

        {/* Overall Score Badge */}
        {results?.adjectival_rating ? (
          <div className="flex items-center gap-2 shrink-0">
            <span
              className={cn(
                'inline-flex items-center rounded-xs px-2.5 py-1 text-xs font-bold uppercase tracking-wider',
                getAdjectivalRatingClasses(results.adjectival_rating),
              )}
            >
              {results.adjectival_rating}
            </span>
            {typeof results.overall_score === 'number' ? (
              <span className="text-xs font-bold tabular-nums text-text">
                ★ {formatScore(results.overall_score)} / 4.0
              </span>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* Main Body */}
      <div className="p-4 sm:p-6 space-y-5 flex-1">
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
                          'mx-0.5 h-px w-3 flex-shrink-0',
                          isCompleted ? 'bg-primary' : 'bg-border',
                        )}
                      />
                    )}
                  </div>
                );
              })}
            </div>

            <div className="mt-3 flex items-center justify-between text-xs text-text-muted pt-2 border-t border-border">
              <span>{statusMessage(status?.status, Boolean(isFailedWithResults), isPartial)}</span>
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

        {/* Perspective Domain Tabs */}
        <div className="rounded-md border border-border bg-surface overflow-hidden">
          <div
            className="flex flex-wrap gap-1 border-b border-border bg-surface-subtle px-3 py-1.5"
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
                    'flex items-center gap-2 rounded-sm px-3 py-2 text-xs font-semibold transition-colors cursor-pointer select-none',
                    isActive
                      ? 'bg-surface text-primary border border-border shadow-xs'
                      : 'text-text-muted hover:text-text hover:bg-surface/50 border border-transparent',
                  )}
                >
                  <Icon className="size-3.5" aria-hidden="true" />
                  <span>{agentShortLabel(agent.id)}</span>

                  {agentState !== 'pending' && (
                    <span
                      className={cn(
                        'ml-0.5 rounded-xs px-1.5 py-0.2 text-[9px] font-bold uppercase tracking-tight tabular-nums',
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
                  <h3 className={TYPOGRAPHY.headingSm}>{selectedAgent.name}</h3>
                  {domainScore?.version != null ? (
                    <Badge variant="neutral">Revision {domainScore.version}</Badge>
                  ) : null}
                  {domainScore?.version == null &&
                    (results?.legacy_notice || domainScore?.form_snapshot_id == null) &&
                    results && (
                      <Badge variant="neutral">Legacy — form snapshot unavailable</Badge>
                    )}
                </div>
                <p className="text-xs text-text-muted mt-1 leading-relaxed max-w-2xl">
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

          {/* Ordered Criteria Table */}
          <div className="overflow-x-auto">
            <table className={TABLE_STYLES.table}>
              <thead className={TABLE_STYLES.thead}>
                <tr>
                  <th scope="col" className={cn(TABLE_STYLES.th, 'w-20 text-center')}>
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
                  selectedScore.rows.map((row) => (
                    <tr key={row.criterion} className={TABLE_STYLES.tr}>
                      {/* Rating Number */}
                      <td className="px-4 py-3.5 text-center align-top">
                        <span className="inline-flex size-7 items-center justify-center rounded-xs bg-surface-subtle border border-border text-xs font-bold text-text tabular-nums">
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
                            <span className="font-semibold text-text leading-snug flex-1">
                              {row.criterion}
                            </span>
                            {row.isUngrounded ? (
                              <Badge variant="warning" className="shrink-0">
                                Ungrounded
                              </Badge>
                            ) : null}
                          </div>
                          {row.description ? (
                            <p className="text-xs text-text-muted mt-0.5 leading-relaxed pl-0.5">
                              {row.description}
                            </p>
                          ) : null}
                        </div>
                      </td>

                      {/* Status */}
                      <td className={cn(TABLE_STYLES.td, 'text-right align-top')}>
                        <span className="text-xs font-semibold text-text-muted whitespace-nowrap">
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))
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

        {/* Feedback Panel */}
        <FeedbackPanel criteria={selectedScore.feedbackCriteria} />

        {/* Next Steps Card */}
        {isTerminal && evaluationId ? (
          <div className="rounded-md border border-border bg-surface p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
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
