import { Fragment, useMemo, useState } from 'react';
import { Outlet, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Loader2, CheckCircle, Flag } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import { useEvaluation } from '../hooks/useEvaluationStatus';
import { evaluationApi } from '../api/evaluation.api';
import { formatScore, cleanJustification, overallScoreDisplay } from '../utils/scoreHelpers';
import { ScorecardPdfExport } from './ScorecardPdfExport';
import { AgentReviewModal } from './AgentReviewModal';

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

export function Scorecard() {
  const { id } = useParams({ strict: false }) as { id?: string };

  const { data: evaluation, isLoading, isError } = useEvaluation(id ?? '');
  const [reviewModalAgent, setReviewModalAgent] = useState<'itso' | 'sme' | null>(null);

  const isTerminal = evaluation?.status === 'COMPLETED' || evaluation?.status === 'FAILED';
  const isFailed = evaluation?.status === 'FAILED';

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
    retry: 1,
  });

  const hasResults = results && Object.keys(results.domain_scores).length > 0;
  const isFailedWithResults = isFailed && hasResults;
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
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-canvas">
        <div className="flex flex-col items-center gap-4 text-text-muted border border-border bg-surface p-8 rounded-sm">
          <Loader2 className="size-8 animate-spin text-primary" />
          <p className="text-xs font-bold uppercase tracking-wider text-text">Loading evaluation status...</p>
        </div>
      </div>
    );
  }

  if (isError || !evaluation) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-canvas">
        <div className="flex flex-col items-center gap-4 text-destructive border border-destructive/20 bg-surface p-8 rounded-sm">
          <AlertTriangle className="size-8 text-destructive" />
          <p className="text-sm font-bold uppercase tracking-wider">
            Failed to load evaluation details.
          </p>
        </div>
      </div>
    );
  }

  return (
    <section className="flex h-[calc(100vh-4rem)] flex-col bg-canvas">
      {/* Compact Header Row */}
      <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-surface px-6">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span className="text-[10px] font-extrabold uppercase tracking-widest text-text-muted select-none">
            Report Ledger
          </span>
          <h1
            className="truncate text-sm font-bold text-text select-all"
            title={evaluation.evaluation_id}
          >
            Job ID: {evaluation.evaluation_id}
          </h1>
          {isTerminal && (
            <span
              className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider ${
                isFailed && !isFailedWithResults
                  ? 'border-destructive/40 text-destructive bg-destructive-soft'
                  : isFailedWithResults || isPartial
                    ? 'border-warning/45 text-warning bg-warning-soft'
                    : 'border-primary/40 text-primary bg-primary-soft'
              }`}
            >
              {isPartial ? 'Partial' : evaluation.status.replace('_', ' ')}
            </span>
          )}
        </div>

        {results &&
          (() => {
            const display = overallScoreDisplay({
              overallScore: results.overall_score,
              synthesizedScore: results.synthesized_score,
            });
            return (
              <div className="flex shrink-0 items-center gap-4 select-none">
                <div className="flex items-center gap-1.5 border border-border bg-surface-subtle px-2.5 py-1 rounded-sm text-[10px] font-bold uppercase tracking-wider text-text">
                  <span>Overall:</span>
                  <span className="text-primary font-extrabold">{display.canonicalText}</span>
                  <span className="text-text-muted">({display.monitoringText} monitoring)</span>
                </div>
                <ScorecardPdfExport results={results} />
              </div>
            );
          })()}
      </header>

      {/* Main Ledger workspace */}
      <main className="flex-1 overflow-y-auto bg-canvas p-6">
        {/* Unified Ledger Summary block */}
        <div className="mx-auto max-w-[90rem] border border-border bg-surface p-6 rounded-sm mb-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 select-none">
            {!isTerminal && <Loader2 className="size-5 animate-spin text-primary" />}
            {isTerminal && (!isFailed || isFailedWithResults) && (
              <CheckCircle className="size-5 text-success" />
            )}
            {isFailed && !isFailedWithResults && (
              <AlertTriangle className="size-5 text-destructive" />
            )}

            <div>
              <h2 className="text-xs font-bold text-text uppercase tracking-widest">
                {isPartial && evaluation.status === 'COMPLETED'
                  ? 'Partial Evaluation Completed'
                  : `Evaluation status: ${evaluation.status.replace('_', ' ').toLowerCase()}`}
              </h2>
            </div>
          </div>

          <div className="mt-4">
            {/* Metadata information table-style grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-[11px] leading-relaxed">
              <div className="border border-border bg-surface-subtle p-3 rounded-sm">
                <span className="font-extrabold text-text-muted uppercase tracking-wider block mb-1">
                  Target Document
                </span>
                <span
                  className="font-bold text-text block truncate"
                  title={results?.document_title || evaluation.document_id}
                >
                  {results?.document_title || evaluation.document_id}
                </span>
              </div>

              <div className="border border-border bg-surface-subtle p-3 rounded-sm">
                <span className="font-extrabold text-text-muted uppercase tracking-wider block mb-1">
                  Syllabus Reference
                </span>
                <span className="font-bold text-text block">
                  {evaluation.syllabus_id ?? '—'}
                </span>
              </div>

              <div className="border border-border bg-surface-subtle p-3 rounded-sm">
                <span className="font-extrabold text-text-muted uppercase tracking-wider block mb-1">
                  Curriculum Reference
                </span>
                <span className="font-bold text-text block">
                  {evaluation.curriculum_id ?? '—'}
                </span>
              </div>

              <div className="border border-border bg-surface-subtle p-3 rounded-sm">
                <span className="font-extrabold text-text-muted uppercase tracking-wider block mb-1">
                  Submitted At
                </span>
                <span className="font-bold text-text block">
                  {new Date(evaluation.submitted_at).toLocaleString()}
                </span>
              </div>

              {evaluation.completed_at && (
                <div className="border border-border bg-surface-subtle p-3 rounded-sm">
                  <span className="font-extrabold text-text-muted uppercase tracking-wider block mb-1">
                    Finished At
                  </span>
                  <span className="font-bold text-text block">
                    {new Date(evaluation.completed_at).toLocaleString()}
                  </span>
                </div>
              )}

              {evaluation.completed_at && results?.duration_seconds != null && (
                <div className="border border-border bg-surface-subtle p-3 rounded-sm">
                  <span className="font-extrabold text-text-muted uppercase tracking-wider block mb-1">
                    Evaluation Time
                  </span>
                  <span className="font-bold text-text block tabular-nums">
                    {formatDuration(results.duration_seconds)}
                  </span>
                </div>
              )}
            </div>

            {/* Legacy notice */}
            {results?.legacy_notice && (
              <div className="mt-4 rounded-sm border border-border bg-surface-subtle px-3 py-2 text-xs font-semibold text-text leading-relaxed">
                {results.legacy_notice}
              </div>
            )}

            {/* Advisory status alert */}
            {isPartial && (
              <div className="mt-4 rounded-sm border border-warning/30 bg-warning-soft px-3 py-2 text-xs text-warning leading-relaxed">
                <strong>Partial evaluation:</strong>{' '}
                {partialReason ||
                  'This evaluation ran without a curriculum reference. Coordinator review was skipped.'}
              </div>
            )}

            {isFailed && evaluation.error_message && (
              <div className="mt-4 rounded-sm border border-destructive/20 bg-destructive-soft p-3 text-xs text-destructive">
                <p className="font-bold">Error Details</p>
                <p className="mt-1 font-mono leading-normal whitespace-pre-wrap">
                  {evaluation.error_message}
                </p>
              </div>
            )}
          </div>
        </div>

        {isTerminal && isLoadingResults && (
          <div className="flex justify-center py-12">
            <Loader2 className="size-6 animate-spin text-primary" />
          </div>
        )}

        {isTerminal && isResultsError && (
          <div className="mx-auto max-w-[90rem] rounded-sm border border-destructive/20 bg-destructive-soft p-6 mb-8 text-destructive">
            <div className="flex items-start gap-3">
              <AlertTriangle className="size-5 shrink-0" />
              <div className="flex-1">
                <p className="font-bold uppercase tracking-wider text-xs">
                  Failed to load evaluation results
                </p>
                <p className="mt-1 text-sm">
                  {resultsError instanceof Error
                    ? resultsError.message
                    : 'Results could not be retrieved. Try refreshing the page.'}
                </p>
                <button
                  type="button"
                  onClick={() => refetchResults()}
                  className="mt-3 inline-flex h-8 items-center justify-center border border-destructive/30 hover:bg-destructive/10 text-destructive px-3 rounded-sm text-xs font-bold uppercase tracking-wide transition-colors cursor-pointer"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        {results && (
          <div className="mx-auto max-w-[90rem] space-y-6">
            {/* Dynamic Evaluation Flags Overview */}
            {results.flags && results.flags.length > 0 && (
              <div className="rounded-sm border border-warning/30 bg-warning-soft p-5">
                <div className="flex items-center gap-2 mb-4 text-warning select-none">
                  <Flag className="size-4.5 text-warning fill-current" />
                  <h3 className="text-xs font-bold uppercase tracking-wider">Evaluation Flags</h3>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {results.flags.map((flag) => (
                    <div
                      key={flag.flag_id}
                      className="bg-surface rounded-sm p-4 border border-warning/30 text-xs"
                    >
                      <div className="flex items-center gap-2 mb-2 select-none">
                        <span className="inline-flex items-center rounded-sm bg-warning-soft px-2 py-0.5 text-[9px] font-extrabold text-warning border border-warning/40 uppercase tracking-wider">
                          {agentLabels[flag.agent_id] ? flag.agent_id.toUpperCase() : flag.agent_id}
                        </span>
                        <span className="font-bold text-text-muted tabular-nums">
                          Score: {formatScore(flag.score)}/4
                        </span>
                      </div>
                      <h4 className="font-bold text-text leading-normal">
                        {flag.criterion_text}
                      </h4>
                      {flag.justification && (
                        <p className="text-text-muted mt-1.5 leading-relaxed bg-surface-subtle p-2 border border-border rounded-sm">
                          {cleanJustification(flag.justification)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Structured Criteria Ledger Table */}
            <div className="border border-border bg-surface rounded-sm overflow-hidden">
              <table className="w-full text-left border-collapse border-spacing-0">
                <thead className="bg-surface-subtle border-b border-border select-none">
                  <tr>
                    <th className="py-3 px-4 font-bold text-[10px] uppercase tracking-widest text-text-muted">
                      Evaluation Criterion & Justification
                    </th>
                    <th className="py-3 px-4 font-bold text-[10px] uppercase tracking-widest text-text-muted w-[6rem] text-right">
                      Score
                    </th>
                    <th className="py-3 px-4 font-bold text-[10px] uppercase tracking-widest text-text-muted w-[10rem]">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {domainKeys.map((domain) => {
                    const domainData = results.domain_scores[domain];
                    const isSkipped = isPartial && domain === 'coordinator' && !domainData;

                    if (isSkipped) {
                      return (
                        <tr key={`${domain}-skipped`} className="bg-surface-subtle/30">
                          <td colSpan={3} className="py-4 px-4">
                            <div className="flex items-center gap-2 select-none">
                              <span className="inline-flex shrink-0 items-center rounded-sm bg-warning-soft text-warning px-2 py-0.5 text-[9px] font-extrabold border border-warning/30 uppercase tracking-widest">
                                {domain.toUpperCase()} SKIPPED
                              </span>
                              <span className="text-xs text-text-muted font-medium">
                                Program Coordinator curriculum-grounded review was skipped because
                                no curriculum reference was available.
                              </span>
                            </div>
                          </td>
                        </tr>
                      );
                    }
                    if (!domainData) return null;

                    const isDomainError = domainData.status === 'ERROR';

                    return (
                      <Fragment key={domain}>
                        {/* Domain Group Header Row */}
                        <tr className="bg-surface-subtle/70 select-none">
                          <td className="py-3 px-4 text-[10px] font-extrabold text-text uppercase tracking-widest border-t border-border">
                            <div className="flex flex-wrap items-center gap-2.5">
                              <span>{agentLabels[domain] || domain.toUpperCase()}</span>
                              {domainData.version != null && (
                                <span className="inline-flex items-center rounded-sm border border-border bg-surface px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-text">
                                  Revision {domainData.version}
                                </span>
                              )}
                              {domainData.version == null &&
                                (results.legacy_notice || domainData.form_snapshot_id == null) && (
                                  <span className="inline-flex items-center rounded-sm border border-border bg-surface-subtle px-2 py-0.5 text-[9px] font-bold text-text-muted">
                                    Legacy — form snapshot unavailable
                                  </span>
                                )}
                              {domainData.adapter_key && (
                                <span className="text-[9px] font-mono font-normal text-text-muted">
                                  ({domainData.adapter_key} v{domainData.adapter_version ?? 1})
                                </span>
                              )}
                              {(domain === 'itso' || domain === 'sme') && (
                                <button
                                  type="button"
                                  className="shrink-0 rounded-sm border border-primary/30 bg-primary-soft px-2 py-1 text-[9px] font-bold normal-case tracking-wide text-primary hover:bg-primary-soft/80"
                                  onClick={() => setReviewModalAgent(domain as 'itso' | 'sme')}
                                >
                                  Review Scores
                                </button>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right w-[6rem] border-t border-border">
                            <span className="text-xs font-bold text-text-muted tabular-nums">
                              Subtotal: {formatScore(domainData.subtotal)}/
                              {formatScore(domainData.max_score)}
                            </span>
                          </td>
                          <td className="py-3 px-4 w-[10rem] border-t border-border">
                            {domainData.adjectival_rating && (
                              <span
                                className={cn(
                                  'inline-flex items-center rounded-sm border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                                  getAdjectivalRatingClasses(domainData.adjectival_rating),
                                )}
                              >
                                {domainData.adjectival_rating}
                              </span>
                            )}
                          </td>
                        </tr>

                        {/* Criterion Detail Rows with inline Justification */}
                        {domainData.criteria.map((criterion, idx) => {
                          const rating = Number(criterion.score);
                          const isWeak = !Number.isNaN(rating) && rating < 2;
                          const isUngrounded = Boolean(criterion.is_ungrounded);
                          return (
                            <tr
                              key={`${domain}-${criterion.criterion_id || idx}`}
                              className={cn(
                                isUngrounded
                                  ? 'bg-warning-soft/30 hover:bg-warning-soft/50'
                                  : isWeak
                                    ? 'bg-destructive-soft/30 hover:bg-destructive-soft/50'
                                    : 'hover:bg-surface-subtle/30',
                                'transition-colors border-b border-border last:border-b-0',
                              )}
                            >
                              <td className="py-4 px-4 text-text align-top">
                                <div className="flex items-start justify-between gap-2">
                                  <div className="text-sm font-semibold">
                                    <span className="font-mono text-xs font-bold text-text-muted mr-2">
                                      {criterion.criterion_id}
                                    </span>
                                    <span>{criterion.criterion_text}</span>
                                  </div>
                                  {isUngrounded && (
                                    <span className="shrink-0 inline-flex items-center rounded-sm border border-warning/40 bg-warning-soft px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider text-warning">
                                      Ungrounded
                                    </span>
                                  )}
                                </div>
                                {criterion.description && (
                                  <p className="mt-1 text-xs text-text-muted leading-normal">
                                    {criterion.description}
                                  </p>
                                )}
                                {criterion.justification && (
                                  <div className="mt-2 text-xs leading-[1.6] text-text-muted bg-surface-subtle p-2.5 border border-border rounded-sm font-medium">
                                    {cleanJustification(criterion.justification)}
                                  </div>
                                )}
                                {criterion.evidence && (
                                  <div className="mt-2 text-xs leading-relaxed text-text-muted bg-surface-subtle/50 p-2 border border-border rounded-sm font-normal">
                                    <span className="font-semibold text-text">Evidence: </span>
                                    {cleanJustification(criterion.evidence)}
                                  </div>
                                )}
                              </td>
                              <td className="py-4 px-4 text-right align-top w-[6rem]">
                                <span className="inline-flex h-7 min-w-[2.5rem] items-center justify-center rounded-sm border border-border bg-surface px-2 text-xs font-sans font-bold text-text tabular-nums">
                                  {formatScore(criterion.score)}/4
                                </span>
                              </td>
                              <td className="py-4 px-4 align-top w-[10rem]">
                                <span
                                  className={cn(
                                    'inline-flex items-center rounded-sm border px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider',
                                    isDomainError
                                      ? 'border-destructive/30 bg-destructive-soft text-destructive'
                                      : isUngrounded
                                        ? 'border-warning/40 bg-warning-soft text-warning'
                                        : isWeak
                                          ? 'border-destructive/30 bg-destructive-soft text-destructive'
                                          : 'border-success/30 bg-success-soft text-success',
                                  )}
                                >
                                  {isDomainError
                                    ? 'Failed'
                                    : isUngrounded
                                      ? 'Ungrounded'
                                      : isWeak
                                        ? 'Needs attention'
                                        : 'Acceptable'}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {reviewModalAgent && results.domain_scores[reviewModalAgent] && (
              <AgentReviewModal
                agentName={reviewModalAgent}
                evaluationId={evaluation.evaluation_id}
                criteria={results.domain_scores[reviewModalAgent].criteria}
                onClose={() => setReviewModalAgent(null)}
              />
            )}
          </div>
        )}
      </main>

      <Outlet />
    </section>
  );
}
