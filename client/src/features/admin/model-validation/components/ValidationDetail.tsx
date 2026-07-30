import { Link } from '@tanstack/react-router';
import { AlertTriangle, ChevronDown, ChevronRight, Loader2, ShieldAlert } from 'lucide-react';
import { getErrorMessage } from '@/shared/api/http';
import { cn } from '@/shared/components/utils';
import {
  useModelValidationDetail,
  useModelValidationEvaluation,
} from '../hooks/useModelValidationQueries';
import type { ModelValidationCriterionScore, ModelValidationItem } from '../types';
import {
  formatTimestamp,
  groupCriteriaByAgent,
  HISTORY_COLSPAN,
  statusClass,
} from '../utils/helpers';

export type HistoryRowProps = {
  item: ModelValidationItem;
  isExpanded: boolean;
  isAnyExpanded: boolean;
  comparedCount: number;
  exactMatches: number;
  onToggle: () => void;
  onClose: () => void;
};

export function HistoryRow({
  item,
  isExpanded,
  isAnyExpanded: _isAnyExpanded,
  comparedCount,
  exactMatches,
  onToggle,
  onClose,
}: HistoryRowProps) {
  const expansionId = `validation-detail-${item.validation_id}`;
  return (
    <>
      <tr className={cn(isExpanded && 'bg-slate-50/60')}>
        <td className="px-4 py-3 font-semibold text-slate-900">
          {item.document_title ?? 'Untitled SLM'}
        </td>
        <td className="px-4 py-3">
          <span
            className={`inline-flex rounded-sm px-2 py-1 text-xs font-bold ${statusClass(item.status)}`}
          >
            {item.status}
          </span>
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {item.criterion_scores.length}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">{comparedCount}</td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {comparedCount ? `${exactMatches}/${comparedCount}` : '—'}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {item.absolute_error == null ? '—' : item.absolute_error.toFixed(2)}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {item.latency_seconds == null ? '—' : `${item.latency_seconds.toFixed(2)} s`}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {item.score_perplexity == null ? '—' : item.score_perplexity.toFixed(2)}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums">
          {item.toxicity_score == null ? (
            <span title={item.toxicity_error ?? 'Assessment pending'}>—</span>
          ) : (
            <span
              title={`${item.toxicity_label ?? 'Assessed'}: ${item.toxicity_explanation ?? 'No explanation available'}`}
            >
              {(item.toxicity_score * 100).toFixed(2)}%
            </span>
          )}
        </td>
        <td className="px-4 py-3 text-right">
          {item.status === 'COMPLETED' ||
          item.status === 'FAILED' ||
          item.criterion_scores.length > 0 ? (
            <button
              type="button"
              onClick={onToggle}
              aria-expanded={isExpanded}
              aria-controls={expansionId}
              className="inline-flex items-center gap-1 rounded-sm font-bold text-[#1b3b87] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
            >
              {isExpanded ? (
                <ChevronDown className="size-4" aria-hidden="true" />
              ) : (
                <ChevronRight className="size-4" aria-hidden="true" />
              )}
              {isExpanded ? 'Hide details' : 'Open evaluation'}
            </button>
          ) : item.error_message ? (
            <span className="text-xs font-semibold text-[#b91c1c]">{item.error_message}</span>
          ) : (
            '—'
          )}
        </td>
      </tr>
      {isExpanded ? (
        <tr>
          <td colSpan={HISTORY_COLSPAN} className="bg-slate-50/60 px-0 py-0">
            <ValidationDetail
              id={expansionId}
              validationId={item.validation_id}
              evaluationId={item.evaluation_id}
              fallbackCriteria={item.criterion_scores}
              partialWithoutCurriculum={item.partial_without_curriculum}
              overallStatus={item.status}
              errorMessage={item.error_message}
              isExpanded={isExpanded}
              onClose={onClose}
            />
          </td>
        </tr>
      ) : null}
    </>
  );
}

type ValidationDetailProps = {
  id: string;
  validationId: string;
  evaluationId: string;
  fallbackCriteria: ModelValidationCriterionScore[];
  partialWithoutCurriculum: boolean;
  overallStatus: ModelValidationItem['status'];
  errorMessage: string | null;
  isExpanded: boolean;
  onClose: () => void;
};

export function ValidationDetail({
  id,
  validationId,
  evaluationId,
  fallbackCriteria,
  partialWithoutCurriculum,
  overallStatus,
  errorMessage,
  isExpanded,
  onClose,
}: ValidationDetailProps) {
  const detailQuery = useModelValidationDetail(validationId, isExpanded);
  const evaluationQuery = useModelValidationEvaluation(validationId, isExpanded);

  const criteria = detailQuery.data?.criterion_scores?.length
    ? detailQuery.data.criterion_scores
    : fallbackCriteria;
  const grouped = groupCriteriaByAgent(criteria);
  const isTerminal = overallStatus === 'COMPLETED' || overallStatus === 'FAILED';
  const evaluation = evaluationQuery.data;
  const isCoordinatorSkipped = partialWithoutCurriculum;

  return (
    <section
      id={id}
      role="region"
      aria-label={`Validation details for ${validationId}`}
      className="grid gap-4 border-t border-slate-200 bg-white px-4 py-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
            Per-agent criterion detail
          </h3>
          <p className="mt-1 text-xs font-medium text-slate-600">
            Expected vs. actual scores for every agent criterion. Pending values reflect evaluation
            state; unavailable values reflect completed runs that did not record a score.
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-sm border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-slate-700 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
        >
          Close
        </button>
      </div>

      {isCoordinatorSkipped ? (
        <p
          role="note"
          className="flex items-start gap-2 rounded-sm border border-[#f2c811] bg-[#f2c811]/10 px-3 py-2 text-xs font-semibold text-slate-800"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-[#1e293b]" aria-hidden="true" />
          <span className="leading-relaxed">
            This validation ran without a curriculum reference. Coordinator curriculum-grounded
            review was skipped. SME, GAD, and ITSO scores below are from the partial run.
          </span>
        </p>
      ) : null}

      {detailQuery.isLoading ? (
        <p
          role="status"
          className="flex items-center gap-2 rounded-sm border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-600"
        >
          <Loader2 className="size-4 animate-spin text-[#1b3b87]" aria-hidden="true" />
          Loading criterion detail…
        </p>
      ) : null}

      {detailQuery.isError ? (
        <p
          role="alert"
          className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-3 py-2 text-xs font-semibold text-[#b91c1c]"
        >
          {getErrorMessage(
            detailQuery.error,
            'Unable to load the criterion detail for this validation.',
          )}
        </p>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-2">
        {grouped.map(({ agentId, agentName, criteria: agentCriteria }) => {
          const isAgentSkipped = agentId === 'coordinator' && isCoordinatorSkipped;
          return (
            <article key={agentId} className="overflow-hidden rounded-sm border border-slate-200">
              <header className="flex items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                  {agentName}
                </h4>
                {isAgentSkipped ? (
                  <span className="inline-flex items-center gap-1 rounded-sm bg-slate-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-700">
                    <ShieldAlert className="size-3" aria-hidden="true" />
                    Skipped — no curriculum
                  </span>
                ) : null}
              </header>
              {isAgentSkipped ? (
                <p className="px-3 py-3 text-xs font-medium leading-relaxed text-slate-600">
                  Coordinator scoring was skipped for this run. No expected, actual, or error values
                  are reported.
                </p>
              ) : (
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="bg-white text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Criterion</th>
                      <th className="px-3 py-2 text-right">Expected</th>
                      <th className="px-3 py-2 text-right">Actual</th>
                      <th className="px-3 py-2 text-right">Error</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {agentCriteria.map((score) => {
                      const expected = score.expected_score;
                      const actual = score.actual_score;
                      const error = score.absolute_error;
                      const actualLabel =
                        actual == null ? (isTerminal ? 'Unavailable' : 'Pending') : String(actual);
                      const errorLabel =
                        error == null ? (isTerminal ? 'Unavailable' : 'Pending') : error.toFixed(2);
                      return (
                        <tr key={score.expected_score_id}>
                          <th scope="row" className="px-3 py-2 font-semibold text-slate-900">
                            <span className="block break-words">
                              {score.criterion_id} · {score.criterion_title}
                            </span>
                          </th>
                          <td className="px-3 py-2 text-right font-semibold tabular-nums text-slate-900">
                            {expected}
                          </td>
                          <td className="px-3 py-2 text-right font-semibold tabular-nums text-slate-900">
                            {actual == null ? (
                              <span
                                className={cn(
                                  'inline-block rounded-sm px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                                  isTerminal
                                    ? 'bg-[#b91c1c]/10 text-[#b91c1c]'
                                    : 'bg-slate-100 text-slate-600',
                                )}
                              >
                                {actualLabel}
                              </span>
                            ) : (
                              actualLabel
                            )}
                          </td>
                          <td className="px-3 py-2 text-right font-semibold tabular-nums text-slate-900">
                            {error == null ? (
                              <span
                                className={cn(
                                  'inline-block rounded-sm px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
                                  isTerminal
                                    ? 'bg-[#b91c1c]/10 text-[#b91c1c]'
                                    : 'bg-slate-100 text-slate-600',
                                )}
                              >
                                {errorLabel}
                              </span>
                            ) : (
                              errorLabel
                            )}
                          </td>
                        </tr>
                      );
                    })}
                    {agentCriteria.length === 0 ? (
                      <tr>
                        <td
                          colSpan={4}
                          className="px-3 py-3 text-center text-xs font-medium text-slate-500"
                        >
                          No criteria recorded for this agent.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              )}
            </article>
          );
        })}
        {grouped.length === 0 ? (
          <p className="rounded-sm border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
            No criteria have been recorded for this validation yet.
          </p>
        ) : null}
      </div>

      <section
        aria-label="Linked evaluation"
        className="grid gap-3 rounded-sm border border-slate-200 bg-white p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
            Linked evaluation
          </h3>
          {evaluation ? (
            <span
              className={`inline-flex rounded-sm px-2 py-1 text-xs font-bold ${statusClass(evaluation.status as ModelValidationItem['status'])}`}
            >
              {evaluation.status}
            </span>
          ) : evaluationQuery.isLoading ? (
            <span className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600">
              <Loader2 className="size-3 animate-spin text-[#1b3b87]" aria-hidden="true" />
              Loading evaluation status…
            </span>
          ) : null}
        </div>
        <p className="text-xs leading-relaxed text-slate-600">
          The evaluation job is accessed through the admin-linked evaluation endpoint so admins can
          review benchmark runs that another admin submitted. Faculty cannot reach this surface.
        </p>
        {evaluationQuery.isError ? (
          <p
            role="alert"
            className="rounded-sm border border-[#b91c1c]/30 bg-[#b91c1c]/10 px-3 py-2 text-xs font-semibold text-[#b91c1c]"
          >
            {getErrorMessage(
              evaluationQuery.error,
              'Unable to load the linked evaluation for this validation.',
            )}
          </p>
        ) : null}
        {evaluation ? (
          <dl className="grid gap-2 sm:grid-cols-2">
            <EvaluationMetaItem label="Evaluation ID" value={evaluation.evaluation_id} mono />
            <EvaluationMetaItem label="Status" value={evaluation.status} emphasize />
            <EvaluationMetaItem
              label="Submitted"
              value={formatTimestamp(evaluation.submitted_at)}
            />
            <EvaluationMetaItem
              label="Completed"
              value={formatTimestamp(evaluation.completed_at)}
            />
            <EvaluationMetaItem
              label="Duration"
              value={
                evaluation.duration_seconds == null
                  ? '—'
                  : `${evaluation.duration_seconds.toFixed(2)} s`
              }
            />
            <EvaluationMetaItem
              label="Partial"
              value={evaluation.partial_without_curriculum ? 'Yes' : 'No'}
            />
            {evaluation.partial_reason ? (
              <EvaluationMetaItem
                label="Partial reason"
                value={evaluation.partial_reason}
                fullWidth
              />
            ) : null}
            {evaluation.error_message ? (
              <EvaluationMetaItem label="Error" value={evaluation.error_message} error fullWidth />
            ) : null}
            {errorMessage && !evaluation.error_message ? (
              <EvaluationMetaItem label="Run error" value={errorMessage} error fullWidth />
            ) : null}
          </dl>
        ) : null}
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-3 text-xs font-semibold text-slate-700">
          <Link
            to="/evaluations/$id"
            params={{ id: evaluationId }}
            className="inline-flex items-center gap-1 rounded-sm border border-slate-200 bg-white px-3 py-1.5 font-bold text-[#1b3b87] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
          >
            Open scorecard
          </Link>
          <span className="text-xs font-medium text-slate-500">
            Opens the evaluation scorecard for this validation.
          </span>
        </div>
      </section>
    </section>
  );
}

function EvaluationMetaItem({
  label,
  value,
  mono = false,
  emphasize = false,
  error = false,
  fullWidth = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  emphasize?: boolean;
  error?: boolean;
  fullWidth?: boolean;
}) {
  return (
    <div
      className={cn(
        'grid grid-cols-[7rem_1fr] items-baseline gap-2 border-b border-slate-200 pb-2 last:border-b-0',
        fullWidth && 'sm:col-span-2',
      )}
    >
      <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</dt>
      <dd
        className={cn(
          'text-xs leading-relaxed',
          mono && 'font-mono break-all text-slate-700',
          emphasize && 'font-semibold text-slate-900',
          !mono && !emphasize && 'font-medium text-slate-700',
          error && 'font-semibold text-[#b91c1c]',
        )}
      >
        {value}
      </dd>
    </div>
  );
}
