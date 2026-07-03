import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Circle,
  Clock,
  Eye,
  Loader2,
  Lightbulb,
  Scale,
  ShieldCheck,
  Target,
  XCircle,
} from 'lucide-react';
import { useNavigate } from '@tanstack/react-router';
import { cn } from '@/shared/components/utils';
import { getErrorMessage } from '@/shared/api/http';
import { FeedbackPanel } from './FeedbackPanel';
import { formatScore } from './scoreHelpers';
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
    icon: Scale,
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
): 'pending' | 'running' | 'done' | 'failed' {
  if (!results) return 'pending';
  if (results.failed_agents?.includes(agentId)) return 'failed';
  if (results.domain_scores[agentId]) return 'done';
  if (results.active_agents?.includes(agentId)) return 'running';
  return 'pending';
}

function getScoreRingColor(score: number): string {
  if (score >= 85) return '#3b963e'; // Verification Green
  if (score >= 70) return '#f2c811'; // SCC Amber Gold
  return '#b91c1c'; // Destructive Red
}

function getAdjectivalRatingColor(rating: string | undefined): string {
  switch (rating) {
    case 'Very Satisfactory':
      return '#3b963e';
    case 'Satisfactory':
      return '#3eaed4';
    case 'Needs Improvement':
      return '#f2c811';
    case 'Poor':
      return '#b91c1c';
    default:
      return '#64748b';
  }
}

function getAdjectivalRatingClasses(rating: string | undefined): string {
  switch (rating) {
    case 'Very Satisfactory':
      return 'bg-[#3b963e]/10 text-[#3b963e] border-[#3b963e]/30';
    case 'Satisfactory':
      return 'bg-[#3eaed4]/10 text-[#3eaed4] border-[#3eaed4]/30';
    case 'Needs Improvement':
      return 'bg-[#f2c811]/10 text-[#1e293b] border-[#f2c811]/30';
    case 'Poor':
      return 'bg-[#b91c1c]/10 text-[#b91c1c] border-[#b91c1c]/30';
    default:
      return 'bg-slate-50 text-slate-500 border-slate-200';
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
      return 'bg-[#3b963e]/10 text-[#3b963e] border-[#3b963e]/30';
    case 'medium':
      return 'bg-[#f2c811]/10 text-[#1e293b] border-[#f2c811]/30';
    case 'weak':
      return 'bg-[#b91c1c]/10 text-[#b91c1c] border-[#b91c1c]/30';
    default:
      return 'bg-slate-50 text-slate-500 border-slate-200';
  }
}

function statusMessage(status: string | undefined, isFailedWithResults: boolean): string {
  if (isFailedWithResults) {
    return 'Evaluation failed, but partial results are available for review.';
  }
  switch (status) {
    case 'SUBMITTED':
      return 'Job submitted. Waiting to start preprocessing…';
    case 'PREPROCESSING':
      return 'Preprocessing document contents and preparing chunks for evaluation…';
    case 'EVALUATING':
      return 'Running multi-agent evaluation across all review domains…';
    case 'SYNTHESIZING':
      return 'Synthesizing agent reports and computing final scores…';
    case 'COMPLETED':
      return 'Evaluation completed. Review the scores and criteria below.';
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
      ? `Subtotal ${formatScore(domainScore.subtotal)} of ${formatScore(domainScore.max_score)} weighted points${results?.is_partial || isFailedWithResults ? ' (partial)' : ''}.`
      : isInProgress
        ? 'Evaluation in progress...'
        : isFailedWithResults
          ? 'Evaluation failed, but partial results are available.'
          : 'Evaluation results are not available yet.',
    feedbackCriteria: domainScore?.criteria || [],
    rows: (domainScore?.criteria ?? []).map((criterion: CriterionScoreItem) => ({
      rating: formatScore(criterion.score),
      criterion: criterion.criterion_text,
      status: getShortStatusLabel(criterion.score),
    })),
  };

  const scoreRingColor = domainScore ? getScoreRingColor(selectedScore.score) : '#e2e8f0';

  const handleViewFullReport = () => {
    if (evaluationId) {
      void navigate({ to: '/evaluations/$id', params: { id: evaluationId } });
    }
  };

  return (
    <section className="min-h-0 overflow-y-auto bg-white">
      <div className="flex min-h-44 items-center justify-between gap-6 border-b px-10">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
            Evaluation Report
          </p>
          <h2 className="mt-3 text-2xl font-semibold tracking-normal">Synthesized Agent View</h2>
          <p className="mt-2 text-base text-slate-500">
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
                <span className="text-sm font-semibold text-slate-500">
                  {formatScore(results.overall_score)} of 4
                </span>
              )}
            </div>
          )}
        </div>
        {domainScore ? (
          <div
            className="grid size-28 place-items-center rounded-full border-4 bg-white p-3"
            style={{ borderColor: scoreRingColor }}
          >
            <div className="text-center">
              <div className="text-3xl font-bold text-slate-900">{selectedScore.score}</div>
              <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                score
              </div>
            </div>
          </div>
        ) : (
          <div className="grid size-28 place-items-center rounded-full border-2 border-dashed border-slate-200 bg-white p-3">
            <div className="text-center">
              <Loader2 className="mx-auto size-6 animate-spin text-slate-500" aria-hidden="true" />
              <div className="mt-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
                {isInProgress ? 'Running...' : submitIsPending ? 'Submitting...' : 'No data'}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="px-10 py-8">
        {evaluationId && (
          <div className="mb-6">
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
                          isUpcoming && 'border border-muted-foreground/30 text-slate-500',
                        )}
                      >
                        {isCompleted && <CheckCircle2 className="size-3.5" aria-hidden="true" />}
                        {isCurrent && (
                          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                        )}
                        {isUpcoming && <Circle className="size-3.5" aria-hidden="true" />}
                      </span>
                      <span
                        className={cn(
                          'text-[10px] font-semibold uppercase tracking-wider',
                          isCompleted && 'text-primary',
                          isCurrent && 'text-primary',
                          isUpcoming && 'text-slate-500',
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
            {status?.status === 'FAILED' && (
              <div className="mt-3 flex items-center justify-between gap-3 rounded-md bg-[#b91c1c]/5 px-3 py-2">
                <div className="flex items-center gap-2">
                  <XCircle className="size-4 shrink-0 text-[#b91c1c]" aria-hidden="true" />
                  <span className="text-sm font-medium text-[#b91c1c]">
                    {isFailedWithResults
                      ? 'Evaluation failed, but partial results are available for review.'
                      : 'Evaluation failed. No results were produced.'}
                  </span>
                </div>
                <button
                  type="button"
                  className="shrink-0 inline-flex h-8 items-center gap-1.5 border border-[#b91c1c]/30 hover:bg-[#b91c1c]/10 text-[#b91c1c] px-3 rounded-sm text-xs font-bold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#b91c1c]/30 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none"
                  onClick={handleRetryEvaluation}
                  disabled={isResolvingEval || submitIsPending}
                >
                  <AlertTriangle className="size-3.5" aria-hidden="true" />
                  Retry Evaluation
                </button>
              </div>
            )}
            {status?.status !== 'FAILED' && (
              <div className="mt-3 flex items-center gap-3">
                <p className="text-sm font-medium text-slate-500">
                  {statusMessage(status?.status, Boolean(isFailedWithResults))}
                </p>
                {isTerminal && (results?.duration_seconds != null || status?.duration_seconds != null) && (
                  <span
                    className="inline-flex items-center gap-1 rounded-sm border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[11px] font-semibold tabular-nums text-slate-600"
                    title="Total evaluation duration"
                  >
                    <Clock className="size-3" aria-hidden="true" />
                    {formatDuration(results?.duration_seconds ?? status?.duration_seconds)}
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        {isResultsError && isTerminal && (
          <div className="mt-4 rounded-lg border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-4 py-3 text-sm text-[#b91c1c]">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div className="flex-1">
                <p className="font-medium">Failed to load results</p>
                <p className="mt-1 text-[#b91c1c]/80">
                  {getErrorMessage(resultsError, 'Results could not be retrieved.')}
                </p>
                <button
                  type="button"
                  className="mt-2 inline-flex h-8 items-center justify-center border border-[#b91c1c]/30 hover:bg-[#b91c1c]/10 text-[#b91c1c] px-3 rounded-sm text-xs font-bold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#b91c1c]/30 focus:outline-none"
                  onClick={() => refetchResults()}
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        <p className="mb-4 mt-8 text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
          Evaluation Agent
        </p>
        <div className="grid gap-3 xl:grid-cols-2">
          {agents.map((agent) => {
            const Icon = agent.icon;
            const isActive = agent.id === selectedAgentId;
            const agentState = getAgentCardState(agent.id, results);

            return (
              <button
                key={agent.name}
                type="button"
                onClick={() => onSelectAgent(agent.id)}
                className={cn(
                  'flex min-h-20 flex-wrap items-center gap-4 rounded-sm border border-slate-200 p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
                  isActive
                    ? 'border-slate-900 bg-foreground text-background'
                    : 'bg-white hover:bg-slate-50/60',
                )}
                aria-pressed={isActive}
              >
                <span
                  className={cn(
                    'grid size-12 shrink-0 place-items-center rounded-lg',
                    isActive ? 'bg-white/15' : 'bg-slate-50',
                  )}
                >
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{agent.name}</span>
                  <span
                    className={cn(
                      'mt-1 block text-sm',
                      isActive ? 'text-background/75' : 'text-slate-500',
                    )}
                  >
                    {agent.subtitle}
                  </span>
                </span>
                {agentState !== 'pending' && (
                  <span
                    className={cn(
                      'ml-auto flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
                      agentState === 'done' && 'bg-[#3b963e]/10 text-[#3b963e]',
                      agentState === 'running' && 'bg-primary/10 text-primary',
                      agentState === 'failed' && 'bg-[#b91c1c]/10 text-[#b91c1c]',
                    )}
                  >
                    {agentState === 'done' && (
                      <CheckCircle2 className="size-3" aria-hidden="true" />
                    )}
                    {agentState === 'running' && (
                      <Loader2 className="size-3 animate-spin" aria-hidden="true" />
                    )}
                    {agentState === 'failed' && <XCircle className="size-3" aria-hidden="true" />}
                    {agentState === 'done'
                      ? 'Complete'
                      : agentState === 'running'
                        ? 'Running'
                        : 'Failed'}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <section className="mt-10 grid gap-5">
          <div
            className={cn(
              'rounded-sm border bg-white p-5',
              selectedScore.score >= 85 && 'border-[#3b963e]/30 bg-[#3b963e]/10',
              selectedScore.score >= 70 &&
                selectedScore.score < 85 &&
                'border-[#f2c811]/30 bg-[#f2c811]/10',
              selectedScore.score < 70 && domainScore && 'border-[#b91c1c]/30 bg-[#b91c1c]/10',
            )}
          >
            <div className="flex items-start gap-4">
              {(() => {
                const agentState = getAgentCardState(selectedAgent.id, results);
                if (agentState === 'done') {
                  return (
                    <CheckCircle2
                      className="mt-1 size-5 shrink-0 text-[#3b963e]"
                      aria-hidden="true"
                    />
                  );
                }
                if (agentState === 'running') {
                  return (
                    <Loader2
                      className="mt-1 size-5 shrink-0 animate-spin text-primary"
                      aria-hidden="true"
                    />
                  );
                }
                if (agentState === 'failed') {
                  return (
                    <XCircle className="mt-1 size-5 shrink-0 text-[#b91c1c]" aria-hidden="true" />
                  );
                }
                return <Clock className="mt-1 size-5 shrink-0 text-slate-500" aria-hidden="true" />;
              })()}
              <div className="min-w-0 flex-1">
                <h3 className="text-lg font-semibold">{selectedAgent.name}</h3>
                <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-500">
                  {selectedScore.summary}
                </p>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              {domainScore ? (
                <span
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-bold',
                    selectedScore.score >= 85 && 'bg-[#3b963e] text-white',
                    selectedScore.score >= 70 &&
                      selectedScore.score < 85 &&
                      'bg-[#f2c811] text-[#1e293b]',
                    selectedScore.score < 70 && 'bg-[#b91c1c] text-white',
                  )}
                >
                  <Target className="size-3.5" aria-hidden="true" />
                  {selectedScore.score}% score
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm text-slate-500">
                  <Clock className="size-3.5" aria-hidden="true" />
                  {isInProgress ? 'Evaluating…' : 'No data'}
                </span>
              )}
              {selectedScore.verdict === 'Acceptable' && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#3b963e] px-3 py-1.5 text-sm font-semibold text-white">
                  <CheckCircle2 className="size-3.5" aria-hidden="true" />
                  Acceptable
                </span>
              )}
              {selectedScore.verdict === 'Review recommended' && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f2c811] px-3 py-1.5 text-sm font-semibold text-[#1e293b]">
                  <AlertTriangle className="size-3.5" aria-hidden="true" />
                  Review recommended
                </span>
              )}
              {selectedScore.verdict === 'Failed' && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#b91c1c] px-3 py-1.5 text-sm font-semibold text-white">
                  <XCircle className="size-3.5" aria-hidden="true" />
                  Failed
                </span>
              )}
              {(selectedScore.verdict === 'Waiting…' || selectedScore.verdict === '—') && (
                <span className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium text-slate-500">
                  <Clock className="size-3.5" aria-hidden="true" />
                  {selectedScore.verdict}
                </span>
              )}
            </div>
          </div>

          <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
            <table className="w-full text-left border-collapse border-spacing-0">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4 font-semibold text-[11px] uppercase tracking-wider text-slate-500 w-[8rem]">
                    Rating
                  </th>
                  <th className="py-3 px-4 font-semibold text-[11px] uppercase tracking-wider text-slate-500">
                    Evaluation Criterion
                  </th>
                  <th className="py-3 px-4 font-semibold text-[11px] uppercase tracking-wider text-slate-500 w-[14rem]">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {selectedScore.rows.length > 0 ? (
                  selectedScore.rows.map((row) => {
                    const tier = getCriterionTier(row.rating);
                    const isWeak = tier === 'weak';
                    return (
                      <tr
                        key={row.criterion}
                        className={cn(
                          isWeak && 'bg-[#b91c1c]/5 hover:bg-[#b91c1c]/10',
                          'hover:bg-slate-50/50',
                        )}
                      >
                        <td className="py-3 px-4 text-sm font-medium">
                          <span
                            className={cn(
                              'inline-grid size-8 place-items-center rounded-full border text-xs font-bold',
                              getCriterionStyles(tier),
                            )}
                          >
                            {row.rating}
                          </span>
                        </td>
                        <td
                          className={cn(
                            'py-3 px-4 text-sm whitespace-normal',
                            isWeak ? 'text-slate-900 font-bold' : 'text-slate-600 font-semibold',
                          )}
                        >
                          {row.criterion}
                        </td>
                        <td className="py-3 px-4 text-sm whitespace-normal">
                          <span
                            className={cn(
                              'rounded-sm border px-2.5 py-1 text-xs font-semibold uppercase tracking-wider',
                              isWeak
                                ? 'border-[#b91c1c]/30 bg-[#b91c1c]/10 text-[#b91c1c]'
                                : 'border-slate-200 bg-slate-50 text-slate-500',
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
                      className="py-8 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider bg-slate-50/10"
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

        <section className="mt-8 rounded-sm border border-slate-200 bg-white p-5">
          <div className="flex items-center gap-2">
            <Target className="size-4 text-slate-500" aria-hidden="true" />
            <h3 className="font-semibold">Next Steps</h3>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            This evaluation is advisory until reviewed by an authorized human reviewer. Review the
            criteria and scores above, then open the Full Report for a consolidated view across all
            agents.
          </p>
          {isTerminal && evaluationId && (
            <button
              type="button"
              className="mt-4 inline-flex h-9 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-3.5 rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:ring-2 focus:ring-[#1b3b87] focus:outline-none"
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
