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
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/components/utils';
import { getErrorMessage } from '@/shared/api/http';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
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
  if (score >= 85) return '#16a34a'; // emerald-600
  if (score >= 70) return '#f59e0b'; // amber-500
  return '#f43f5e'; // rose-500
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
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    case 'medium':
      return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'weak':
      return 'bg-rose-50 text-rose-700 border-rose-200';
    default:
      return 'bg-muted text-muted-foreground border-transparent';
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

  const scoreRingColor = domainScore ? getScoreRingColor(selectedScore.score) : 'transparent';
  const scoreRingStyle = {
    background: `conic-gradient(${scoreRingColor} ${selectedScore.score * 3.6}deg, hsl(var(--muted)) 0deg)`,
  };

  const handleViewFullReport = () => {
    if (evaluationId) {
      void navigate({ to: '/evaluations/$id', params: { id: evaluationId } });
    }
  };

  return (
    <section className="min-h-0 overflow-y-auto bg-card">
      <div className="flex min-h-44 items-center justify-between gap-6 border-b px-10">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
            Score Matrix Dashboard
          </p>
          <h2 className="mt-3 text-2xl font-semibold tracking-normal">Synthesized Agent View</h2>
          <p className="mt-2 text-base text-muted-foreground">
            Advisory synthesis - Human review authoritative
          </p>
        </div>
        {domainScore ? (
          <div className="grid size-28 place-items-center rounded-full p-3" style={scoreRingStyle}>
            <div className="grid size-full place-items-center rounded-full bg-background">
              <div className="text-center">
                <div className="text-3xl font-bold">{selectedScore.score}</div>
                <div className="text-xs text-muted-foreground">score</div>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid size-28 place-items-center rounded-full border-2 border-dashed border-muted-foreground/25 p-3">
            <div className="text-center">
              <Loader2
                className="mx-auto size-6 animate-spin text-muted-foreground"
                aria-hidden="true"
              />
              <div className="mt-1 text-xs text-muted-foreground">
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
                          isUpcoming && 'border border-muted-foreground/30 text-muted-foreground',
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
                          isUpcoming && 'text-muted-foreground',
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
              <div className="mt-3 flex items-center justify-between gap-3 rounded-md bg-destructive/5 px-3 py-2">
                <div className="flex items-center gap-2">
                  <XCircle className="size-4 shrink-0 text-destructive" aria-hidden="true" />
                  <span className="text-sm font-medium text-destructive">
                    {isFailedWithResults
                      ? 'Evaluation failed, but partial results are available for review.'
                      : 'Evaluation failed. No results were produced.'}
                  </span>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="shrink-0 gap-1.5 border-destructive/30 text-destructive hover:bg-destructive/10 hover:text-destructive"
                  onClick={handleRetryEvaluation}
                  disabled={isResolvingEval || submitIsPending}
                >
                  <AlertTriangle className="size-3.5" aria-hidden="true" />
                  Retry Evaluation
                </Button>
              </div>
            )}
            {status?.status !== 'FAILED' && (
              <p className="mt-3 text-sm font-medium text-muted-foreground">
                {statusMessage(status?.status, Boolean(isFailedWithResults))}
              </p>
            )}
          </div>
        )}

        {isResultsError && isTerminal && (
          <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div className="flex-1">
                <p className="font-medium">Failed to load results</p>
                <p className="mt-1 text-destructive/80">
                  {getErrorMessage(resultsError, 'Results could not be retrieved.')}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={() => refetchResults()}
                >
                  Retry
                </Button>
              </div>
            </div>
          </div>
        )}

        <p className="mb-4 mt-8 text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
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
                  'flex min-h-20 flex-wrap items-center gap-4 rounded-lg border p-4 text-left shadow-sm transition-colors',
                  isActive
                    ? 'border-foreground bg-foreground text-background'
                    : 'bg-background hover:bg-muted/60',
                )}
                aria-pressed={isActive}
              >
                <span
                  className={cn(
                    'grid size-12 shrink-0 place-items-center rounded-lg',
                    isActive ? 'bg-background/15' : 'bg-muted',
                  )}
                >
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{agent.name}</span>
                  <span
                    className={cn(
                      'mt-1 block text-sm',
                      isActive ? 'text-background/75' : 'text-muted-foreground',
                    )}
                  >
                    {agent.subtitle}
                  </span>
                </span>
                {agentState !== 'pending' && (
                  <span
                    className={cn(
                      'ml-auto flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
                      agentState === 'done' && 'bg-emerald-100 text-emerald-700',
                      agentState === 'running' && 'bg-primary/10 text-primary',
                      agentState === 'failed' && 'bg-destructive/10 text-destructive',
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
              'rounded-xl border bg-background p-5',
              selectedScore.score >= 85 && 'border-emerald-200 bg-emerald-50/30',
              selectedScore.score >= 70 &&
                selectedScore.score < 85 &&
                'border-amber-200 bg-amber-50/30',
              selectedScore.score < 70 && domainScore && 'border-rose-200 bg-rose-50/30',
            )}
          >
            <div className="flex items-start gap-4">
              {(() => {
                const agentState = getAgentCardState(selectedAgent.id, results);
                if (agentState === 'done') {
                  return (
                    <CheckCircle2
                      className="mt-1 size-5 shrink-0 text-emerald-600"
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
                    <XCircle className="mt-1 size-5 shrink-0 text-destructive" aria-hidden="true" />
                  );
                }
                return (
                  <Clock
                    className="mt-1 size-5 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                );
              })()}
              <div className="min-w-0 flex-1">
                <h3 className="text-lg font-semibold">{selectedAgent.name}</h3>
                <p className="mt-1 max-w-3xl text-sm leading-relaxed text-muted-foreground">
                  {selectedScore.summary}
                </p>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              {domainScore ? (
                <span
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-bold',
                    selectedScore.score >= 85 && 'bg-emerald-100 text-emerald-800',
                    selectedScore.score >= 70 &&
                      selectedScore.score < 85 &&
                      'bg-amber-100 text-amber-800',
                    selectedScore.score < 70 && 'bg-rose-100 text-rose-800',
                  )}
                >
                  <Target className="size-3.5" aria-hidden="true" />
                  {selectedScore.score}% score
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm text-muted-foreground">
                  <Clock className="size-3.5" aria-hidden="true" />
                  {isInProgress ? 'Evaluating…' : 'No data'}
                </span>
              )}
              {selectedScore.verdict === 'Acceptable' && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1.5 text-sm font-semibold text-emerald-800">
                  <CheckCircle2 className="size-3.5" aria-hidden="true" />
                  Acceptable
                </span>
              )}
              {selectedScore.verdict === 'Review recommended' && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1.5 text-sm font-semibold text-amber-800">
                  <AlertTriangle className="size-3.5" aria-hidden="true" />
                  Review recommended
                </span>
              )}
              {selectedScore.verdict === 'Failed' && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-100 px-3 py-1.5 text-sm font-semibold text-rose-800">
                  <XCircle className="size-3.5" aria-hidden="true" />
                  Failed
                </span>
              )}
              {(selectedScore.verdict === 'Waiting…' || selectedScore.verdict === '—') && (
                <span className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium text-muted-foreground">
                  <Clock className="size-3.5" aria-hidden="true" />
                  {selectedScore.verdict}
                </span>
              )}
            </div>
          </div>

          <div className="rounded-lg border bg-background">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[8rem] uppercase tracking-[0.18em]">Rating</TableHead>
                  <TableHead className="uppercase tracking-[0.18em]">
                    Evaluation Criterion
                  </TableHead>
                  <TableHead className="w-[14rem] uppercase tracking-[0.18em]">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {selectedScore.rows.length > 0 ? (
                  selectedScore.rows.map((row) => {
                    const tier = getCriterionTier(row.rating);
                    const isWeak = tier === 'weak';
                    return (
                      <TableRow key={row.criterion} className={cn(isWeak && 'bg-rose-50/40')}>
                        <TableCell>
                          <span
                            className={cn(
                              'inline-grid size-9 place-items-center rounded-full border font-semibold text-sm',
                              getCriterionStyles(tier),
                            )}
                          >
                            {row.rating}
                          </span>
                        </TableCell>
                        <TableCell
                          className={cn(
                            'whitespace-normal',
                            isWeak ? 'text-foreground font-medium' : 'text-muted-foreground',
                          )}
                        >
                          {row.criterion}
                        </TableCell>
                        <TableCell className="whitespace-normal">
                          <span
                            className={cn(
                              'rounded-md border px-2.5 py-1 text-xs font-medium',
                              isWeak
                                ? 'border-rose-200 bg-rose-50 text-rose-700'
                                : 'border-muted-foreground/20 bg-background text-muted-foreground',
                            )}
                          >
                            {row.status}
                          </span>
                        </TableCell>
                      </TableRow>
                    );
                  })
                ) : (
                  <TableRow>
                    <TableCell
                      colSpan={3}
                      className="py-8 text-center text-sm text-muted-foreground"
                    >
                      {isInProgress
                        ? 'Criteria will appear once evaluation completes.'
                        : 'No criteria available.'}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          <FeedbackPanel criteria={selectedScore.feedbackCriteria} />
        </section>

        <section className="mt-8 rounded-lg border bg-background p-5">
          <div className="flex items-center gap-2">
            <Target className="size-4 text-muted-foreground" aria-hidden="true" />
            <h3 className="font-semibold">Next Steps</h3>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            This evaluation is advisory until reviewed by an authorized human reviewer. Review the
            criteria and scores above, then open the Full Report for a consolidated view across all
            agents.
          </p>
          {isTerminal && evaluationId && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-4 gap-2"
              onClick={handleViewFullReport}
            >
              <Eye className="size-4" aria-hidden="true" />
              Open Full Report
            </Button>
          )}
        </section>
      </div>
    </section>
  );
}
