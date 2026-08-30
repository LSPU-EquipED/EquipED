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
import { cn } from '@/shared/components/utils';
import { getErrorMessage } from '@/shared/api/http';
import { FeedbackPanel } from './FeedbackPanel';
import { formatScore, agentShortLabel } from '../utils/scoreHelpers';
import { ScorecardPdfExport } from './ScorecardPdfExport';
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

function getScoreRingColor(score: number): string {
  if (score >= 85) return 'var(--success)';
  if (score >= 70) return 'var(--warning)';
  return 'var(--destructive)';
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

function getCriterionStyles(tier: 'strong' | 'medium' | 'weak' | 'unknown') {
  switch (tier) {
    case 'strong':
      return 'bg-success-soft text-success border-success/30';
    case 'medium':
      return 'bg-warning-soft text-warning border-warning/30';
    case 'weak':
      return 'bg-destructive-soft text-destructive border-destructive/30';
    default:
      return 'bg-surface-subtle text-text-muted border-border';
  }
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
  resultsError,
  refetchResults,
  handleRetryEvaluation,
  isResolvingEval,
  submitIsPending,
  evaluationId,
  selectedAgentId,
  onSelectAgent,
}: ScoreDashboardProps) {
  const navigate = useNavigate();

  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0];
  const domainScore = results?.domain_scores[selectedAgent.id];
  const isPartial = Boolean(results?.is_partial || status?.partial_without_curriculum);
  const partialReason = results?.partial_reason || status?.partial_reason;

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
        ? 'Waiting…'
        : '—',
    summary: domainScore
      ? `Subtotal ${formatScore(domainScore.subtotal)} of ${formatScore(domainScore.max_score)} weighted points${isPartial || isFailedWithResults ? ' (partial)' : ''}.`
      : isInProgress
        ? 'Evaluation in progress...'
        : isPartial && selectedAgent.id === 'coordinator'
          ? 'Program Coordinator review was skipped because this evaluation ran without a curriculum reference.'
          : isFailedWithResults
            ? 'Evaluation failed, but partial results are available.'
            : 'Evaluation results are not available yet.',
    feedbackCriteria: domainScore?.criteria || [],
    rows: (domainScore?.criteria ?? []).map((criterion: CriterionScoreItem) => ({
      rating: formatScore(criterion.score),
      code: criterion.criterion_id,
      criterion: criterion.criterion_text,
      description: criterion.description,
      status: criterion.is_ungrounded ? 'Ungrounded' : getShortStatusLabel(criterion.score),
      isUngrounded: Boolean(criterion.is_ungrounded),
    })),
  };

  const scoreRingColor = domainScore ? getScoreRingColor(selectedScore.score) : 'var(--border)';

  const handleViewFullReport = () => {
    if (evaluationId) {
      void navigate({ to: '/evaluations/$id', params: { id: evaluationId } });
    }
  };

  return (
    <section className="min-h-0 overflow-y-auto bg-canvas">
      <div className="flex min-h-44 items-center justify-between gap-6 border-b border-border bg-surface px-10">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-text-muted">
            Evaluation Report
          </p>
          <h2 className="mt-3 text-2xl font-semibold tracking-normal text-text">Synthesized Agent View</h2>
          <p className="mt-2 text-base text-text-muted">
            Advisory synthesis - Human review authoritative
          </p>
          {results?.adjectival_rating && (
            <div className="mt-3 flex items-center gap-3">
              <span
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-sm border px-3 py-1.5 text-sm font-bold uppercase tracking-wider',
                  getAdjectivalRatingClasses(results.adjectival_rating),
                )}
              >
                Overall Rating: {results.adjectival_rating}
              </span>
              {typeof results.overall_score === 'number' && (
                <span className="text-sm font-semibold text-text-muted tabular-nums">
                  {formatScore(results.overall_score)} of 4
                </span>
              )}
            </div>
          )}
          {results && isTerminal && (
            <div className="mt-4">
              <ScorecardPdfExport results={results} />
            </div>
          )}
        </div>
        {domainScore ? (
          <div
            className="grid size-28 place-items-center rounded-full border-4 bg-surface p-3"
            style={{ borderColor: scoreRingColor }}
            title="Monitoring percentage (0-100 scale) derived from the 1-4 canonical subtotal. The adjectival rating below is the canonical 1-4 evaluation."
          >
            <div className="text-center">
              <div className="text-3xl font-bold text-text tabular-nums">{selectedScore.score}</div>
              <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                monitoring %
              </div>
            </div>
          </div>
        ) : (
          <div className="grid size-28 place-items-center rounded-full border-2 border-dashed border-border bg-surface p-3">
            <div className="text-center">
              <Spinner className="mx-auto size-6 animate-spin text-text-muted" aria-hidden="true" />
              <div className="mt-1 text-xs font-semibold uppercase tracking-wider text-text-muted">
                {isInProgress ? 'Running...' : submitIsPending ? 'Submitting...' : 'No data'}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="px-10 py-8">
        {evaluationId && (
          <div className="mb-6">
            {!isTerminal ? (
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
                          'flex flex-1 flex-col items-center gap-1.5 rounded-md py-2',
                          isCurrent && 'bg-primary/5',
                        )}
                      >
                        <span
                          className={cn(
                            'grid size-6 place-items-center rounded-full text-xs font-bold',
                            isCompleted && 'bg-primary text-primary-foreground',
                            isCurrent && 'border-2 border-primary text-primary',
                            isUpcoming && 'border border-border text-text-muted',
                          )}
                        >
                          {isCompleted && <CheckCircle className="size-3.5" aria-hidden="true" />}
                          {isCurrent && (
                            <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
                          )}
                          {isUpcoming && <Circle className="size-3.5" aria-hidden="true" />}
                        </span>
                        <span
                          className={cn(
                            'text-[10px] font-semibold uppercase tracking-wider',
                            isCompleted && 'text-primary',
                            isCurrent && 'text-primary',
                            isUpcoming && 'text-text-muted',
                          )}
                        >
                          {stage.label}
                        </span>
                      </div>
                      {index < PIPELINE_STAGES.length - 1 && (
                        <div
                          className={cn(
                            'mx-1 h-px w-4 flex-shrink-0',
                            isCompleted ? 'bg-primary' : 'bg-border',
                          )}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-sm border border-border bg-surface-subtle px-3 py-2 text-[10px] font-bold text-text-muted uppercase tracking-widest select-none">
                {status?.status === 'COMPLETED' ? (
                  <>
                    <CheckCircle className="size-4 text-success" />
                    <span>Evaluation Matrix Ready</span>
                  </>
                ) : (
                  <>
                    <XCircle className="size-4 text-destructive" />
                    <span>Evaluation pipeline stopped</span>
                  </>
                )}
              </div>
            )}
            {status?.status === 'FAILED' && (
              <div className="mt-3 flex items-center justify-between gap-3 rounded-sm border border-destructive/20 bg-destructive-soft px-3 py-2">
                <div className="flex items-center gap-2">
                  <XCircle className="size-4 shrink-0 text-destructive" aria-hidden="true" />
                  <span className="text-sm font-medium text-destructive">
                    {isFailedWithResults
                      ? 'Evaluation failed, but partial results are available for review.'
                      : 'Evaluation failed. No results were produced.'}
                  </span>
                </div>
                <button
                  type="button"
                  className="shrink-0 inline-flex h-8 items-center gap-1.5 border border-destructive/30 hover:bg-destructive/10 text-destructive px-3 rounded-sm text-xs font-bold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-ring disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none"
                  onClick={handleRetryEvaluation}
                  disabled={isResolvingEval || submitIsPending}
                >
                  <WarningCircle className="size-3.5" aria-hidden="true" />
                  Retry Evaluation
                </button>
              </div>
            )}
            {status?.status !== 'FAILED' && (
              <div className="mt-3 flex items-center gap-3">
                <p className="text-sm font-medium text-text-muted">
                  {statusMessage(status?.status, Boolean(isFailedWithResults), isPartial)}
                </p>
                {isTerminal &&
                  (results?.duration_seconds != null || status?.duration_seconds != null) && (
                    <span
                      className="inline-flex items-center gap-1 rounded-sm border border-border bg-surface-subtle px-2 py-0.5 font-mono text-[11px] font-semibold tabular-nums text-text-muted"
                      title="Total evaluation duration"
                    >
                      <Clock className="size-3 text-text-muted" aria-hidden="true" />
                      {formatDuration(results?.duration_seconds ?? status?.duration_seconds)}
                    </span>
                  )}
              </div>
            )}
            {results?.legacy_notice && (
              <div className="mt-3 rounded-sm border border-border bg-surface-subtle px-3 py-2 text-xs font-bold text-text leading-relaxed">
                {results.legacy_notice}
              </div>
            )}
            {isPartial && (
              <div className="mt-3 rounded-sm border border-warning/30 bg-warning-soft px-3 py-2">
                <div className="flex items-start gap-2">
                  <WarningCircle
                    className="mt-0.5 size-4 shrink-0 text-warning"
                    aria-hidden="true"
                  />
                  <p className="text-sm leading-relaxed text-warning">
                    <strong>Partial evaluation:</strong>{' '}
                    {partialReason
                      ? partialReason
                      : 'This evaluation ran without a curriculum reference. SME, GAD, and ITSO reviews are included, but Program Coordinator curriculum-grounded review was skipped.'}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {isResultsError && isTerminal && (
          <div className="mt-4 rounded-sm border border-destructive/20 bg-destructive-soft px-4 py-3 text-sm text-destructive">
            <div className="flex items-start gap-3">
              <WarningCircle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
              <div className="flex-1">
                <p className="font-medium">Failed to load results</p>
                <p className="mt-1 text-xs text-destructive">
                  {getErrorMessage(resultsError, 'Results could not be retrieved.')}
                </p>
                <button
                  type="button"
                  className="mt-2 inline-flex h-8 items-center justify-center border border-destructive/30 hover:bg-destructive/10 text-destructive px-3 rounded-sm text-xs font-bold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-ring focus:outline-none"
                  onClick={() => refetchResults()}
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="mt-6 border-b border-border">
          <div
            className="flex flex-wrap gap-1"
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
                    'flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-bold uppercase tracking-wider transition-all focus:outline-none cursor-pointer',
                    isActive
                      ? 'border-primary text-primary'
                      : 'border-transparent text-text-muted hover:text-text hover:border-border',
                  )}
                >
                  <Icon className="size-3.5" aria-hidden="true" />
                  <span>{agentShortLabel(agent.id)}</span>

                  {agentState !== 'pending' && (
                    <span
                      className={cn(
                        'ml-1 rounded-full px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-tight',
                        agentState === 'done' && 'bg-success-soft text-success border border-success/20',
                        agentState === 'running' && 'bg-primary-soft text-primary border border-primary/20',
                        agentState === 'failed' && 'bg-destructive-soft text-destructive border border-destructive/20',
                        agentState === 'skipped' && 'bg-warning-soft text-warning border border-warning/20',
                      )}
                    >
                      {agentState === 'done' && 'OK'}
                      {agentState === 'running' && 'RUN'}
                      {agentState === 'skipped' && 'SKIP'}
                      {agentState === 'failed' && 'FAIL'}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        <section className="mt-6 grid gap-5">
          <div
            className="rounded-sm border border-border bg-surface p-5"
          >
            <div className="flex items-start gap-4">
              {(() => {
                const agentState = getAgentCardState(selectedAgent.id, results);
                if (agentState === 'done') {
                  return (
                    <CheckCircle
                      className="mt-1 size-5 shrink-0 text-success"
                      aria-hidden="true"
                    />
                  );
                }
                if (agentState === 'running') {
                  return (
                    <Spinner
                      className="mt-1 size-5 shrink-0 animate-spin text-primary"
                      aria-hidden="true"
                    />
                  );
                }
                if (agentState === 'failed') {
                  return (
                    <XCircle className="mt-1 size-5 shrink-0 text-destructive" aria-hidden="true" />
                  );
                }
                return <Clock className="mt-1 size-5 shrink-0 text-text-muted" aria-hidden="true" />;
              })()}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-semibold text-text">{selectedAgent.name}</h3>
                  {domainScore?.version != null && (
                    <span className="inline-flex items-center rounded-sm border border-border bg-surface-subtle px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-text">
                      Revision {domainScore.version}
                    </span>
                  )}
                  {domainScore?.version == null &&
                    (results?.legacy_notice || domainScore?.form_snapshot_id == null) &&
                    results && (
                      <span className="inline-flex items-center rounded-sm border border-border bg-surface-subtle px-2 py-0.5 text-xs font-bold text-text-muted">
                        Legacy — form snapshot unavailable
                      </span>
                    )}
                </div>
                <p className="mt-1 max-w-3xl text-sm leading-relaxed text-text-muted">
                  {selectedScore.summary}
                </p>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              {domainScore ? (
                <span
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-bold tabular-nums',
                    selectedScore.score >= 85 && 'bg-success text-success-foreground',
                    selectedScore.score >= 70 &&
                      selectedScore.score < 85 &&
                      'bg-warning text-warning-foreground',
                    selectedScore.score < 70 && 'bg-destructive text-destructive-foreground',
                  )}
                  title="Monitoring percentage (0-100) derived from the canonical 1-4 subtotal. The adjectival rating below is on the 1-4 scale."
                >
                  <Target className="size-3.5" aria-hidden="true" />
                  {selectedScore.score}% monitoring
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-sm text-text-muted">
                  <Clock className="size-3.5" aria-hidden="true" />
                  {isInProgress ? 'Evaluating…' : 'No data'}
                </span>
              )}
              {selectedScore.verdict === 'Acceptable' && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-success px-3 py-1.5 text-sm font-semibold text-success-foreground">
                  <CheckCircle className="size-3.5" aria-hidden="true" />
                  Acceptable
                </span>
              )}
              {selectedScore.verdict === 'Review recommended' && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-warning px-3 py-1.5 text-sm font-semibold text-warning-foreground">
                  <WarningCircle className="size-3.5" aria-hidden="true" />
                  Review recommended
                </span>
              )}
              {selectedScore.verdict === 'Failed' && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-destructive px-3 py-1.5 text-sm font-semibold text-destructive-foreground">
                  <XCircle className="size-3.5" aria-hidden="true" />
                  Failed
                </span>
              )}
              {(selectedScore.verdict === 'Waiting…' || selectedScore.verdict === '—') && (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-sm font-medium text-text-muted">
                  <Clock className="size-3.5" aria-hidden="true" />
                  {selectedScore.verdict}
                </span>
              )}
            </div>
          </div>

          <div className="border border-border bg-surface rounded-sm overflow-x-auto">
            <table className="w-full text-left border-collapse border-spacing-0">
              <thead className="bg-surface-subtle border-b border-border">
                <tr>
                  <th className="py-3 px-4 font-semibold text-[11px] uppercase tracking-wider text-text-muted w-[8rem]">
                    Rating
                  </th>
                  <th className="py-3 px-4 font-semibold text-[11px] uppercase tracking-wider text-text-muted">
                    Evaluation Criterion
                  </th>
                  <th className="py-3 px-4 font-semibold text-[11px] uppercase tracking-wider text-text-muted w-[14rem]">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {selectedScore.rows.length > 0 ? (
                  selectedScore.rows.map((row) => {
                    const tier = getCriterionTier(row.rating);
                    const isWeak = tier === 'weak';
                    return (
                      <tr
                        key={row.criterion}
                        className={cn(
                          isWeak && 'bg-destructive-soft/30 hover:bg-destructive-soft/50',
                          'hover:bg-surface-subtle/50',
                        )}
                      >
                        <td className="py-3 px-4 text-sm font-medium">
                          <span
                            className={cn(
                              'inline-grid size-8 place-items-center rounded-full border text-xs font-bold tabular-nums',
                              getCriterionStyles(tier),
                            )}
                          >
                            {row.rating}
                          </span>
                        </td>
                        <td
                          className={cn(
                            'py-3 px-4 text-sm whitespace-normal',
                            row.isUngrounded
                              ? 'text-text font-semibold'
                              : isWeak
                                ? 'text-text font-bold'
                                : 'text-text-muted font-semibold',
                          )}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <span className="font-mono text-xs font-bold text-text-muted mr-2">
                                {row.code}
                              </span>
                              <span>{row.criterion}</span>
                              {row.description && (
                                <p className="mt-0.5 text-xs font-normal text-text-muted leading-normal">
                                  {row.description}
                                </p>
                              )}
                            </div>
                            {row.isUngrounded && (
                              <span className="shrink-0 rounded-sm border border-warning/40 bg-warning-soft px-1.5 py-0.5 text-[9px] font-extrabold uppercase tracking-wider text-warning">
                                Ungrounded
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-sm whitespace-normal">
                          <span
                            className={cn(
                              'rounded-sm border px-2.5 py-1 text-xs font-semibold uppercase tracking-wider',
                              row.isUngrounded
                                ? 'border-warning/40 bg-warning-soft text-warning font-bold'
                                : isWeak
                                  ? 'border-destructive/30 bg-destructive-soft text-destructive'
                                  : 'border-border bg-surface-subtle text-text-muted',
                            )}
                          >
                            {row.status}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td
                      colSpan={3}
                      className="py-8 text-center text-xs font-semibold text-text-muted uppercase tracking-wider bg-surface-subtle/10"
                    >
                      {isInProgress
                        ? 'Criteria will appear once evaluation completes.'
                        : 'No criteria available.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <FeedbackPanel criteria={selectedScore.feedbackCriteria} />
        </section>

        <section className="mt-8 rounded-sm border border-border bg-surface p-5">
          <div className="flex items-center gap-2">
            <Target className="size-4 text-text-muted" aria-hidden="true" />
            <h3 className="font-semibold text-text">Next Steps</h3>
          </div>
          <p className="mt-3 text-sm leading-6 text-text-muted">
            This evaluation is advisory until reviewed by an authorized human reviewer. Review the
            criteria and scores above, then open the Full Report for a consolidated view across all
            agents.
          </p>
          {isTerminal && evaluationId && (
            <button
              type="button"
              className="mt-4 inline-flex h-9 items-center justify-center border border-border hover:bg-surface-subtle text-text px-3.5 rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-ring focus:outline-none"
              onClick={handleViewFullReport}
            >
              <Eye className="size-4 mr-1.5" aria-hidden="true" />
              Open Full Report
            </button>
          )}
        </section>
      </div>
    </section>
  );
}
