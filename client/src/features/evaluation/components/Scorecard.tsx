import { Fragment, useMemo, useState } from 'react';
import { Outlet, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Loader2, CheckCircle, Flag, FileText, Clock } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import { useEvaluation } from '../hooks/useEvaluationStatus';
import { evaluationApi } from '../api/evaluation.api';
import { formatScore, cleanJustification, overallScoreDisplay } from '../utils/scoreHelpers';
import { ScorecardPdfExport } from './ScorecardPdfExport';
import { ItsoReviewModal } from './ItsoReviewModal';

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
  const [isItsoReviewOpen, setIsItsoReviewOpen] = useState(false);

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

  const agentLabels: Record<string, string> = useMemo(() => ({
    sme: 'Subject Matter Expert (SME)',
    coordinator: 'Program Coordinator',
    gad: 'Gender and Development (GAD)',
    itso: 'Innovation and IP (ITSO)',
  }), []);

  if (!id) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-slate-500">
        No evaluation ID provided.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-[#f8fafc]">
        <div className="flex flex-col items-center gap-4 text-slate-500 border border-slate-200 bg-white p-8 rounded-sm">
          <Loader2 className="size-8 animate-spin text-[#1b3b87]" />
          <p className="text-xs font-bold uppercase tracking-wider">Loading evaluation status...</p>
        </div>
      </div>
    );
  }

  if (isError || !evaluation) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-[#f8fafc]">
        <div className="flex flex-col items-center gap-4 text-[#b91c1c] border border-[#b91c1c]/20 bg-white p-8 rounded-sm">
          <AlertTriangle className="size-8 text-[#b91c1c]" />
          <p className="text-sm font-bold uppercase tracking-wider">Failed to load evaluation details.</p>
        </div>
      </div>
    );
  }

  return (
    <section className="flex h-[calc(100vh-4rem)] flex-col bg-white">
      {/* Compact Header Row */}
      <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span className="text-[10px] font-extrabold uppercase tracking-widest text-slate-400 select-none">
            Report Ledger
          </span>
          <h1 className="truncate text-sm font-bold text-slate-800 select-all" title={evaluation.evaluation_id}>
            Job ID: {evaluation.evaluation_id}
          </h1>
          {isTerminal && (
            <span
              className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider ${
                isFailed && !isFailedWithResults
                  ? 'border-[#b91c1c]/40 text-[#b91c1c] bg-[#b91c1c]/5'
                  : isFailedWithResults || isPartial
                    ? 'border-[#f2c811]/45 text-[#1e293b] bg-[#f2c811]/10'
                    : 'border-[#1b3b87]/40 text-[#1b3b87] bg-[#1b3b87]/5'
              }`}
            >
              {isPartial ? 'Partial' : evaluation.status.replace('_', ' ')}
            </span>
          )}
        </div>

        {results && (() => {
          const display = overallScoreDisplay({
            overallScore: results.overall_score,
            synthesizedScore: results.synthesized_score,
          });
          return (
            <div className="flex shrink-0 items-center gap-4 select-none">
              <div className="flex items-center gap-1.5 border border-slate-200 bg-slate-50 px-2.5 py-1 rounded-sm text-[10px] font-bold uppercase tracking-wider text-slate-700">
                <span>Overall:</span>
                <span className="text-[#1b3b87] font-extrabold">{display.canonicalText}</span>
                <span className="text-slate-400">({display.monitoringText} monitoring)</span>
              </div>
              <ScorecardPdfExport results={results} />
            </div>
          );
        })()}
      </header>

      {/* Main Ledger workspace */}
      <main className="flex-1 overflow-y-auto bg-[#f8fafc] p-6">
        {/* Unified Ledger Summary block */}
        <div className="mx-auto max-w-[90rem] border border-slate-200 bg-white p-6 rounded-sm mb-6">
          <div className="flex items-center gap-3 border-b border-slate-100 pb-4 select-none">
            {!isTerminal && <Loader2 className="size-5 animate-spin text-[#1b3b87]" />}
            {isTerminal && (!isFailed || isFailedWithResults) && (
              <CheckCircle className="size-5 text-[#3b963e]" />
            )}
            {isFailed && !isFailedWithResults && (
              <AlertTriangle className="size-5 text-[#b91c1c]" />
            )}

            <div>
              <h2 className="text-xs font-bold text-slate-800 uppercase tracking-widest">
                {isPartial && evaluation.status === 'COMPLETED'
                  ? 'Partial Evaluation Completed'
                  : `Evaluation status: ${evaluation.status.replace('_', ' ').toLowerCase()}`}
              </h2>
            </div>
          </div>

          <div className="mt-4">
            {/* Metadata information table-style grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-[11px] leading-relaxed">
              <div className="border border-slate-100 bg-[#f8fafc]/50 p-3 rounded-sm">
                <span className="font-extrabold text-slate-400 uppercase tracking-wider block mb-1">Target Document</span>
                <span className="font-bold text-slate-800 block truncate" title={results?.document_title || evaluation.document_id}>
                  {results?.document_title || evaluation.document_id}
                </span>
              </div>

              <div className="border border-slate-100 bg-[#f8fafc]/50 p-3 rounded-sm">
                <span className="font-extrabold text-slate-400 uppercase tracking-wider block mb-1">Syllabus Reference</span>
                <span className="font-bold text-slate-800 block">
                  {evaluation.syllabus_id ?? '—'}
                </span>
              </div>

              <div className="border border-slate-100 bg-[#f8fafc]/50 p-3 rounded-sm">
                <span className="font-extrabold text-slate-400 uppercase tracking-wider block mb-1">Curriculum Reference</span>
                <span className="font-bold text-slate-800 block">
                  {evaluation.curriculum_id ?? '—'}
                </span>
              </div>

              <div className="border border-slate-100 bg-[#f8fafc]/50 p-3 rounded-sm">
                <span className="font-extrabold text-slate-400 uppercase tracking-wider block mb-1">Submitted At</span>
                <span className="font-bold text-slate-700 block">
                  {new Date(evaluation.submitted_at).toLocaleString()}
                </span>
              </div>

              {evaluation.completed_at && (
                <div className="border border-slate-100 bg-[#f8fafc]/50 p-3 rounded-sm">
                  <span className="font-extrabold text-slate-400 uppercase tracking-wider block mb-1">Finished At</span>
                  <span className="font-bold text-slate-700 block">
                    {new Date(evaluation.completed_at).toLocaleString()}
                  </span>
                </div>
              )}

              {evaluation.completed_at && results?.duration_seconds != null && (
                <div className="border border-slate-100 bg-[#f8fafc]/50 p-3 rounded-sm">
                  <span className="font-extrabold text-slate-400 uppercase tracking-wider block mb-1">Evaluation Time</span>
                  <span className="font-bold text-slate-700 block">
                    {formatDuration(results.duration_seconds)}
                  </span>
                </div>
              )}
            </div>

            {/* Advisory status alert */}
            {isPartial && (
              <div className="mt-4 rounded-sm border border-[#f2c811]/30 bg-[#f2c811]/5 px-3 py-2 text-xs text-[#1e293b] leading-relaxed">
                <strong>Partial evaluation:</strong> {partialReason || 'This evaluation ran without a curriculum reference. Coordinator review was skipped.'}
              </div>
            )}

            {isFailed && evaluation.error_message && (
              <div className="mt-4 rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-3 text-xs text-[#b91c1c]">
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
            <Loader2 className="size-6 animate-spin text-[#1b3b87]" />
          </div>
        )}

        {isTerminal && isResultsError && (
          <div className="mx-auto max-w-[90rem] rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/5 p-6 mb-8 text-[#b91c1c]">
            <div className="flex items-start gap-3">
              <AlertTriangle className="size-5 shrink-0" />
              <div className="flex-1">
                <p className="font-bold uppercase tracking-wider text-xs">Failed to load evaluation results</p>
                <p className="mt-1 text-sm">
                  {resultsError instanceof Error
                    ? resultsError.message
                    : 'Results could not be retrieved. Try refreshing the page.'}
                </p>
                <button
                  type="button"
                  onClick={() => refetchResults()}
                  className="mt-3 inline-flex h-8 items-center justify-center border border-[#b91c1c]/30 hover:bg-[#b91c1c]/10 px-3 rounded-sm text-xs font-bold uppercase tracking-wide transition-colors cursor-pointer"
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
              <div className="rounded-sm border border-[#f2c811]/30 bg-[#f2c811]/5 p-5">
                <div className="flex items-center gap-2 mb-4 text-[#1e293b] select-none">
                  <Flag className="size-4.5 text-[#f2c811] fill-current" />
                  <h3 className="text-xs font-bold uppercase tracking-wider">Evaluation Flags</h3>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {results.flags.map((flag) => (
                    <div
                      key={flag.flag_id}
                      className="bg-white rounded-sm p-4 border border-[#f2c811]/25 text-xs"
                    >
                      <div className="flex items-center gap-2 mb-2 select-none">
                        <span className="inline-flex items-center rounded-sm bg-[#f2c811]/15 px-2 py-0.5 text-[9px] font-extrabold text-[#1e293b] border border-[#f2c811]/35 uppercase tracking-wider">
                          {agentLabels[flag.agent_id] ? flag.agent_id.toUpperCase() : flag.agent_id}
                        </span>
                        <span className="font-bold text-slate-500">
                          Score: {formatScore(flag.score)}/4
                        </span>
                      </div>
                      <h4 className="font-bold text-slate-900 leading-normal">{flag.criterion_text}</h4>
                      {flag.justification && (
                        <p className="text-slate-600 mt-1.5 leading-relaxed bg-slate-50 p-2 border border-slate-100 rounded-sm">
                          {cleanJustification(flag.justification)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Structured Criteria Ledger Table */}
            <div className="border border-slate-200 bg-white rounded-sm overflow-hidden">
              <table className="w-full text-left border-collapse border-spacing-0">
                <thead className="bg-slate-50 border-b border-slate-200 select-none">
                  <tr>
                    <th className="py-3 px-4 font-bold text-[10px] uppercase tracking-widest text-slate-500">
                      Evaluation Criterion & Justification
                    </th>
                    <th className="py-3 px-4 font-bold text-[10px] uppercase tracking-widest text-slate-500 w-[6rem] text-right">
                      Score
                    </th>
                    <th className="py-3 px-4 font-bold text-[10px] uppercase tracking-widest text-slate-500 w-[10rem]">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {(['sme', 'coordinator', 'gad', 'itso'] as const).map((domain) => {
                    const domainData = results.domain_scores[domain];
                    const isSkipped = isPartial && domain === 'coordinator' && !domainData;

                    if (isSkipped) {
                      return (
                        <tr key={`${domain}-skipped`} className="bg-slate-50/20">
                          <td colSpan={3} className="py-4 px-4">
                            <div className="flex items-center gap-2 select-none">
                              <span className="inline-flex shrink-0 items-center rounded-sm bg-[#f2c811]/10 text-[#1e293b] px-2 py-0.5 text-[9px] font-extrabold border border-[#f2c811]/20 uppercase tracking-widest">
                                {domain.toUpperCase()} SKIPPED
                              </span>
                              <span className="text-xs text-slate-500 font-medium">
                                Program Coordinator curriculum-grounded review was skipped because no curriculum reference was available.
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
                        <tr className="bg-slate-50/60 select-none">
                          <td className="py-3 px-4 text-[10px] font-extrabold text-slate-800 uppercase tracking-widest border-t border-slate-200">
                            {agentLabels[domain]}
                          </td>
                          <td className="py-3 px-4 text-right w-[6rem] border-t border-slate-200">
                            <span className="text-xs font-bold text-slate-500">
                              Subtotal: {formatScore(domainData.subtotal)}/{formatScore(domainData.max_score)}
                            </span>
                          </td>
                          <td className="py-3 px-4 w-[10rem] border-t border-slate-200">
                            <div className="flex items-center justify-between gap-2">
                              {domainData.adjectival_rating && (
                                <span className={cn(
                                  'inline-flex items-center rounded-sm border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                                  getAdjectivalRatingClasses(domainData.adjectival_rating)
                                )}>
                                  {domainData.adjectival_rating}
                                </span>
                              )}
                              {domain === 'itso' && (
                                <button
                                  type="button"
                                  className="shrink-0 rounded-sm border border-[#1b3b87]/30 bg-[#1b3b87]/5 px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-[#1b3b87] hover:bg-[#1b3b87]/10"
                                  onClick={() => setIsItsoReviewOpen(true)}
                                >
                                  Review Scores
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>

                        {/* Criterion Detail Rows with inline Justification */}
                        {domainData.criteria.map((criterion, idx) => {
                          const rating = Number(criterion.score);
                          const isWeak = !Number.isNaN(rating) && rating < 2;
                          return (
                            <tr
                              key={`${domain}-${criterion.criterion_id || idx}`}
                              className={cn(
                                isWeak && 'bg-[#b91c1c]/3 hover:bg-[#b91c1c]/5',
                                'hover:bg-slate-50/30 transition-colors border-b border-slate-200 last:border-b-0'
                              )}
                            >
                              <td className="py-4 px-4 text-slate-800 align-top">
                                <div className="text-sm font-semibold">{criterion.criterion_text}</div>
                                {criterion.justification && (
                                  <div className="mt-2 text-xs leading-[1.6] text-slate-600 bg-slate-50 p-2.5 border border-slate-100 rounded-sm font-medium">
                                    {cleanJustification(criterion.justification)}
                                  </div>
                                )}
                              </td>
                              <td className="py-4 px-4 text-right align-top w-[6rem]">
                                <span className="inline-flex h-7 min-w-[2.5rem] items-center justify-center rounded-sm border border-slate-200 bg-white px-2 text-xs font-sans font-bold text-slate-800">
                                  {formatScore(criterion.score)}/4
                                </span>
                              </td>
                              <td className="py-4 px-4 align-top w-[10rem]">
                                <span
                                  className={cn(
                                    'inline-flex items-center rounded-sm border px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider',
                                    isDomainError
                                      ? 'border-[#b91c1c]/30 bg-[#b91c1c]/10 text-[#b91c1c]'
                                      : isWeak
                                        ? 'border-[#b91c1c]/30 bg-[#b91c1c]/10 text-[#b91c1c]'
                                        : 'border-[#3b963e]/30 bg-[#3b963e]/10 text-[#3b963e]'
                                  )}
                                >
                                  {isDomainError ? 'Failed' : isWeak ? 'Needs attention' : 'Acceptable'}
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

            {isItsoReviewOpen && results.domain_scores.itso && (
              <ItsoReviewModal
                evaluationId={evaluation.evaluation_id}
                criteria={results.domain_scores.itso.criteria}
                onClose={() => setIsItsoReviewOpen(false)}
              />
            )}
          </div>
        )}
      </main>

      <Outlet />
    </section>
  );
}
