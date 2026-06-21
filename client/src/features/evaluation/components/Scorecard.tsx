import { Outlet, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  Loader2,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Flag,
} from 'lucide-react';
import { useState } from 'react';
// Separator removed
import { useEvaluation } from '../hooks/useEvaluationStatus';
import { evaluationApi } from '../api/evaluation.api';
import type { CriterionScoreItem } from '../types';
import { formatScore, cleanJustification } from './scoreHelpers';

const STATUS_MESSAGES: Record<string, string> = {
  SUBMITTED: 'Job submitted, waiting to start...',
  PREPROCESSING: 'Preprocessing document contents...',
  EVALUATING: 'Running multi-agent evaluation layer...',
  SYNTHESIZING: 'Synthesizing agent reports...',
  COMPLETED: 'Evaluation completed.',
  FAILED: 'Evaluation failed.',
};

function CriterionItem({ item }: { readonly item: CriterionScoreItem }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border border-slate-200 rounded-sm p-3 bg-slate-50/30">
      <div
        className="flex items-start justify-between gap-4 cursor-pointer hover:opacity-80 transition-opacity"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-1">
          <p className="text-sm font-medium leading-snug">{item.criterion_text}</p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="font-mono text-sm font-bold bg-muted px-2 py-0.5 rounded">
            {formatScore(item.score)}/4
          </span>
          {expanded ? (
            <ChevronUp className="size-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="size-4 text-muted-foreground" />
          )}
        </div>
      </div>
      {expanded && (
        <div className="mt-3 pt-3 border-t text-sm text-muted-foreground">
          <p>
            <strong>Justification:</strong> {cleanJustification(item.justification)}
          </p>
        </div>
      )}
    </div>
  );
}

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
      <div className="flex h-full items-center justify-center p-8 text-muted-foreground">
        No evaluation ID provided.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 text-muted-foreground">
          <Loader2 className="size-8 animate-spin" />
          <p>Loading evaluation...</p>
        </div>
      </div>
    );
  }

  if (isError || !evaluation) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 text-destructive">
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
    <section className="flex h-[calc(100vh-4rem)] flex-col bg-background">
      <header className="flex min-h-24 shrink-0 items-center justify-between gap-4 border-b bg-background px-10">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Evaluation Status
          </p>
          <div className="flex items-center gap-3 mt-2">
            <h1 className="truncate text-2xl font-semibold">Job: {evaluation.evaluation_id}</h1>
            {isTerminal && (
              <span
                className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase ${isFailed && !isFailedWithResults ? 'border-destructive/50 text-destructive bg-destructive/10' : isFailedWithResults ? 'border-amber-500/50 text-amber-600 bg-amber-50' : 'border-primary/50 text-primary bg-primary/10'}`}
              >
                {evaluation.status.replace('_', ' ')}
              </span>
            )}
          </div>
        </div>
        {results && (
          <div className="text-right">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Synthesized Score
            </p>
            <p className="mt-1 text-3xl font-bold text-primary">
              {typeof results.synthesized_score === 'number'
                ? formatScore(results.synthesized_score)
                : '—'}
              <span className="text-lg text-muted-foreground font-normal">/4</span>
            </p>
          </div>
        )}
      </header>

      <main className="flex-1 overflow-y-auto p-10">
        <div className="mx-auto max-w-5xl rounded-sm border border-slate-200 bg-white p-8 mb-8">
          <div className="flex items-center gap-4 border-b pb-6">
            {!isTerminal && <Loader2 className="size-8 animate-spin text-primary" />}
            {isTerminal && (!isFailed || isFailedWithResults) && (
              <CheckCircle className="size-8 text-green-500" />
            )}
            {isFailed && !isFailedWithResults && (
              <AlertTriangle className="size-8 text-destructive" />
            )}

            <div>
              <h2 className="text-xl font-semibold">{evaluation.status.replace('_', ' ')}</h2>
              <p className="text-muted-foreground mt-1">
                {isFailedWithResults
                  ? 'Evaluation failed, but partial results are available below.'
                  : STATUS_MESSAGES[evaluation.status] || 'Processing...'}
              </p>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="font-semibold text-muted-foreground">Target Document</p>
                <p className="mt-1 font-mono">{evaluation.document_id}</p>
              </div>
              <div>
                <p className="font-semibold text-muted-foreground">Syllabus</p>
                <p className="mt-1 font-mono">{evaluation.syllabus_id ?? '—'}</p>
              </div>
              <div>
                <p className="font-semibold text-muted-foreground">Curriculum</p>
                <p className="mt-1 font-mono">{evaluation.curriculum_id ?? '—'}</p>
              </div>
              <div>
                <p className="font-semibold text-muted-foreground">Submitted At</p>
                <p className="mt-1">{new Date(evaluation.submitted_at).toLocaleString()}</p>
              </div>
              {evaluation.completed_at && (
                <div>
                  <p className="font-semibold text-muted-foreground">Finished At</p>
                  <p className="mt-1">{new Date(evaluation.completed_at).toLocaleString()}</p>
                </div>
              )}
            </div>

            {isFailed && evaluation.error_message && (
              <>
                <div className="border-t border-slate-200 my-4" />
                <div className="rounded-sm border border-red-200 bg-red-50 p-4">
                  <p className="font-semibold text-red-705">Error Details</p>
                  <p className="mt-2 text-xs text-red-700 font-mono whitespace-pre-wrap">
                    {evaluation.error_message}
                  </p>
                </div>
              </>
            )}
          </div>
        </div>

        {isTerminal && isLoadingResults && (
          <div className="flex justify-center py-12">
            <Loader2 className="size-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {isTerminal && isResultsError && (
          <div className="mx-auto max-w-5xl rounded-xl border border-destructive/30 bg-destructive/10 p-6 mb-8">
            <div className="flex items-start gap-3 text-destructive">
              <AlertTriangle className="size-6 shrink-0" />
              <div className="flex-1">
                <p className="font-semibold">Failed to load evaluation results</p>
                <p className="mt-1 text-sm text-destructive/80">
                  {resultsError instanceof Error
                    ? resultsError.message
                    : 'Results could not be retrieved. Try refreshing the page.'}
                </p>
                <button
                  type="button"
                  onClick={() => refetchResults()}
                  className="mt-3 inline-flex items-center rounded-md border border-destructive/40 bg-background px-3 py-1.5 text-sm font-medium text-destructive hover:bg-destructive/5"
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
              <div className="rounded-sm border border-orange-200 bg-orange-50/30 p-6">
                <div className="flex items-center gap-2 mb-4 text-orange-700">
                  <Flag className="size-5" />
                  <h3 className="text-lg font-semibold">Evaluation Flags</h3>
                </div>
                <div className="grid gap-3">
                  {results.flags.map((flag) => (
                    <div
                      key={flag.flag_id}
                      className="bg-white rounded-sm p-4 border border-orange-100 text-xs font-semibold"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className="inline-flex items-center rounded-full border border-orange-200 bg-orange-50 px-2.5 py-0.5 text-xs font-semibold text-orange-700 uppercase">
                          {agentLabels[flag.agent_id] || flag.agent_id}
                        </span>
                        <span className="font-medium text-orange-900">
                          Score: {formatScore(flag.score)}/4
                        </span>
                      </div>
                      <p className="font-medium mb-1">{flag.criterion_text}</p>
                      {flag.justification && (
                        <p className="text-muted-foreground mt-2 text-xs">
                          {cleanJustification(flag.justification)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-6">
              {['sme', 'coordinator', 'gad', 'itso'].map((domain) => {
                const domainData = results.domain_scores[domain];
                if (!domainData) return null;

                const isError = domainData.status === 'ERROR';

                return (
                  <div
                    key={domain}
                    className="flex flex-col rounded-sm border border-slate-200 bg-white overflow-hidden h-[600px]"
                  >
                    <div
                      className={`p-5 border-b border-slate-200 shrink-0 ${isError ? 'bg-red-50' : 'bg-slate-50/50'}`}
                    >
                      <div className="flex justify-between items-center mb-2">
                        <h3 className="font-bold text-lg uppercase tracking-wider text-foreground/80">
                          {agentLabels[domain]}
                        </h3>
                        {isError ? (
                          <XCircle className="size-6 text-destructive" />
                        ) : (
                          <CheckCircle className="size-6 text-green-500" />
                        )}
                      </div>
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-3xl font-extrabold tracking-tight">
                          {formatScore(domainData.subtotal)}
                        </span>
                        <span className="text-muted-foreground font-medium text-lg">
                          / {formatScore(domainData.max_score)}
                        </span>
                      </div>
                    </div>
                    <div className="p-4 flex-1 space-y-3 bg-muted/10 overflow-y-auto">
                      {domainData.criteria.map((criterion, idx) => (
                        <CriterionItem key={criterion.criterion_id || idx} item={criterion} />
                      ))}
                      {domainData.criteria.length === 0 && (
                        <p className="text-sm text-muted-foreground italic text-center mt-8">
                          No criteria evaluated.
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>

      <Outlet />
    </section>
  );
}
