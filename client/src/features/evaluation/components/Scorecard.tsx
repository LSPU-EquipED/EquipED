import { Outlet, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Loader2, CheckCircle, XCircle, Flag } from 'lucide-react';
import { cn } from '@/shared/components/utils';
import { useEvaluation } from '../hooks/useEvaluationStatus';
import { evaluationApi } from '../api/evaluation.api';
import { formatScore, cleanJustification } from './scoreHelpers';

const STATUS_MESSAGES: Record<string, string> = {
  SUBMITTED: 'Job submitted, waiting to start...',
  PREPROCESSING: 'Preprocessing document contents...',
  EVALUATING: 'Running multi-agent evaluation layer...',
  SYNTHESIZING: 'Synthesizing agent reports...',
  COMPLETED: 'Evaluation completed.',
  FAILED: 'Evaluation failed.',
};

export function Scorecard() {
  const { id } = useParams({ strict: false }) as { id?: string };

  const { data: evaluation, isLoading, isError } = useEvaluation(id ?? '');

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

  if (!id) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-slate-500">
        No evaluation ID provided.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-white">
        <div className="flex flex-col items-center gap-4 text-slate-500">
          <Loader2 className="size-8 animate-spin" />
          <p>Loading evaluation...</p>
        </div>
      </div>
    );
  }

  if (isError || !evaluation) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-white">
        <div className="flex flex-col items-center gap-4 text-[#b91c1c]">
          <AlertTriangle className="size-8" />
          <p>Failed to load evaluation. It may not exist or you might not have access.</p>
        </div>
      </div>
    );
  }

  const agentLabels: Record<string, string> = {
    sme: 'SME',
    coordinator: 'Coordinator',
    gad: 'GAD',
    itso: 'ITSO',
  };

  return (
    <section className="flex h-[calc(100vh-4rem)] flex-col bg-white">
      <header className="flex min-h-24 shrink-0 items-center justify-between gap-4 border-b bg-white px-10">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Evaluation Status
          </p>
          <div className="flex items-center gap-3 mt-2">
            <h1 className="truncate text-2xl font-semibold">Job: {evaluation.evaluation_id}</h1>
            {isTerminal && (
              <span
                className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase ${isFailed && !isFailedWithResults ? 'border-[#b91c1c]/50 text-[#b91c1c] bg-[#b91c1c]/10' : isFailedWithResults ? 'border-[#f2c811]/50 text-[#1e293b] bg-[#f2c811]/10' : 'border-[#1b3b87]/50 text-[#1b3b87] bg-[#1b3b87]/10'}`}
              >
                {evaluation.status.replace('_', ' ')}
              </span>
            )}
          </div>
        </div>
        {results && (
          <div className="text-right">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Synthesized Score
            </p>
            <p className="mt-1 text-3xl font-bold text-primary">
              {typeof results.synthesized_score === 'number'
                ? formatScore(results.synthesized_score)
                : '—'}
              <span className="text-lg text-slate-500 font-normal">/4</span>
            </p>
          </div>
        )}
      </header>

      <main className="flex-1 overflow-y-auto p-10">
        <div className="mx-auto max-w-5xl rounded-sm border border-slate-200 bg-white p-8 mb-8">
          <div className="flex items-center gap-4 border-b pb-6">
            {!isTerminal && <Loader2 className="size-8 animate-spin text-primary" />}
            {isTerminal && (!isFailed || isFailedWithResults) && (
              <CheckCircle className="size-8 text-[#3b963e]" />
            )}
            {isFailed && !isFailedWithResults && (
              <AlertTriangle className="size-8 text-[#b91c1c]" />
            )}

            <div>
              <h2 className="text-xl font-semibold">{evaluation.status.replace('_', ' ')}</h2>
              <p className="text-slate-500 mt-1">
                {isFailedWithResults
                  ? 'Evaluation failed, but partial results are available below.'
                  : STATUS_MESSAGES[evaluation.status] || 'Processing...'}
              </p>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="font-semibold text-slate-500">Target Document</p>
                <p className="mt-1 font-sans tabular-nums">{evaluation.document_id}</p>
              </div>
              <div>
                <p className="font-semibold text-slate-500">Syllabus</p>
                <p className="mt-1 font-sans tabular-nums">{evaluation.syllabus_id ?? '—'}</p>
              </div>
              <div>
                <p className="font-semibold text-slate-500">Curriculum</p>
                <p className="mt-1 font-sans tabular-nums">{evaluation.curriculum_id ?? '—'}</p>
              </div>
              <div>
                <p className="font-semibold text-slate-500">Submitted At</p>
                <p className="mt-1">{new Date(evaluation.submitted_at).toLocaleString()}</p>
              </div>
              {evaluation.completed_at && (
                <div>
                  <p className="font-semibold text-slate-500">Finished At</p>
                  <p className="mt-1">{new Date(evaluation.completed_at).toLocaleString()}</p>
                </div>
              )}
            </div>

            {isFailed && evaluation.error_message && (
              <>
                <div className="border-t border-slate-200 my-4" />
                <div className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 p-4">
                  <p className="font-semibold text-[#b91c1c]">Error Details</p>
                  <p className="mt-2 text-xs text-[#b91c1c] font-sans tabular-nums whitespace-pre-wrap">
                    {evaluation.error_message}
                  </p>
                </div>
              </>
            )}
          </div>
        </div>

        {isTerminal && isLoadingResults && (
          <div className="flex justify-center py-12">
            <Loader2 className="size-8 animate-spin text-slate-500" />
          </div>
        )}

        {isTerminal && isResultsError && (
          <div className="mx-auto max-w-5xl rounded-xl border border-[#b91c1c]/30 bg-[#b91c1c]/10 p-6 mb-8">
            <div className="flex items-start gap-3 text-[#b91c1c]">
              <AlertTriangle className="size-6 shrink-0" />
              <div className="flex-1">
                <p className="font-semibold">Failed to load evaluation results</p>
                <p className="mt-1 text-sm text-[#b91c1c]/80">
                  {resultsError instanceof Error
                    ? resultsError.message
                    : 'Results could not be retrieved. Try refreshing the page.'}
                </p>
                <button
                  type="button"
                  onClick={() => refetchResults()}
                  className="mt-3 inline-flex items-center rounded-md border border-[#b91c1c]/40 bg-white px-3 py-1.5 text-sm font-medium text-[#b91c1c] hover:bg-[#b91c1c]/5"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        {results && (
          <div className="mx-auto max-w-[90rem] space-y-8">
            {results.flags && results.flags.length > 0 && (
              <div className="rounded-sm border border-[#f2c811]/30 bg-[#f2c811]/10 p-6">
                <div className="flex items-center gap-2 mb-4 text-[#1e293b]">
                  <Flag className="size-5 text-[#f2c811]" />
                  <h3 className="text-lg font-semibold">Evaluation Flags</h3>
                </div>
                <div className="grid gap-3">
                  {results.flags.map((flag) => (
                    <div
                      key={flag.flag_id}
                      className="bg-white rounded-sm p-4 border border-[#f2c811]/20 text-xs font-semibold"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className="inline-flex items-center rounded-full bg-[#f2c811] px-2.5 py-0.5 text-xs font-semibold text-[#1e293b] uppercase">
                          {agentLabels[flag.agent_id] || flag.agent_id}
                        </span>
                        <span className="font-medium text-[#1e293b]">
                          Score: {formatScore(flag.score)}/4
                        </span>
                      </div>
                      <p className="font-medium mb-1">{flag.criterion_text}</p>
                      {flag.justification && (
                        <p className="text-slate-500 mt-2 text-xs">
                          {cleanJustification(flag.justification)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="border border-slate-200 bg-white rounded-sm overflow-hidden">
              <table className="w-full text-left border-collapse border-spacing-0">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4 font-semibold text-[11px] uppercase tracking-wider text-slate-500 w-[10rem]">
                      Agent
                    </th>
                    <th className="py-3 px-4 font-semibold text-[11px] uppercase tracking-wider text-slate-500">
                      Evaluation Criterion
                    </th>
                    <th className="py-3 px-4 font-semibold text-[11px] uppercase tracking-wider text-slate-500 w-[6rem] text-right">
                      Score
                    </th>
                    <th className="py-3 px-4 font-semibold text-[11px] uppercase tracking-wider text-slate-500 w-[10rem]">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {(['sme', 'coordinator', 'gad', 'itso'] as const).map((domain) => {
                    const domainData = results.domain_scores[domain];
                    if (!domainData) return null;

                    const isError = domainData.status === 'ERROR';
                    return domainData.criteria.map((criterion, idx) => {
                      const rating = Number(criterion.score);
                      const isWeak = !Number.isNaN(rating) && rating < 2;
                      return (
                        <tr
                          key={`${domain}-${criterion.criterion_id || idx}`}
                          className={cn(isWeak && 'bg-[#b91c1c]/5', 'hover:bg-slate-50/50')}
                        >
                          {idx === 0 ? (
                            <td
                              rowSpan={domainData.criteria.length || 1}
                              className="py-3 px-4 align-top border-r border-slate-200 bg-slate-50/30"
                            >
                              <div className="font-bold text-sm text-slate-800">
                                {agentLabels[domain]}
                              </div>
                              <div className="mt-1 text-xs text-slate-500 font-sans tabular-nums">
                                {formatScore(domainData.subtotal)} /{' '}
                                {formatScore(domainData.max_score)}
                              </div>
                            </td>
                          ) : null}
                          <td className="py-3 px-4 text-sm text-slate-700">
                            {criterion.criterion_text}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <span className="inline-flex h-7 min-w-[2.5rem] items-center justify-center rounded-sm border border-slate-200 bg-slate-50 px-2 text-sm font-sans tabular-nums font-bold text-slate-800">
                              {formatScore(criterion.score)}/4
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={cn(
                                'inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-semibold uppercase tracking-wider',
                                isError
                                  ? 'border-[#b91c1c]/30 bg-[#b91c1c]/10 text-[#b91c1c]'
                                  : isWeak
                                    ? 'border-[#b91c1c]/30 bg-[#b91c1c]/10 text-[#b91c1c]'
                                    : 'border-[#3b963e]/30 bg-[#3b963e]/10 text-[#3b963e]',
                              )}
                            >
                              {isError ? 'Failed' : isWeak ? 'Needs attention' : 'Acceptable'}
                            </span>
                          </td>
                        </tr>
                      );
                    });
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      <Outlet />
    </section>
  );
}
