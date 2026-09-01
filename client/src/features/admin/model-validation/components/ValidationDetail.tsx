import { Link } from '@tanstack/react-router';
import {
  CaretDown,
  CaretRight,
  CheckCircle,
  FilePdf,
  ShieldWarning,
  Spinner,
  Warning,
  WarningCircle,
} from '@phosphor-icons/react';
import { getErrorMessage } from '@/shared/api/http';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/components/utils';
import {
  useModelValidationDetail,
  useModelValidationEvaluation,
} from '../hooks/useModelValidationQueries';
import type { ModelValidationCriterionScore, ModelValidationItem } from '../types';
import {
  agentLabel,
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

function formatMaeBadge(mae: number | null | undefined) {
  if (mae == null) return <span className="text-text-muted font-medium">—</span>;
  const isExcellent = mae <= 0.25;
  const isModerate = mae <= 0.5;

  return (
    <span
      className={cn(
        'inline-block px-1.5 py-0.5 rounded-xs font-mono font-bold text-xs tabular-nums border',
        isExcellent
          ? 'bg-success-soft text-success border-success/30'
          : isModerate
            ? 'bg-warning-soft text-warning border-warning/30'
            : 'bg-destructive-soft text-destructive border-destructive/30',
      )}
    >
      {mae.toFixed(2)}
    </span>
  );
}

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
      <tr className={cn(isExpanded && 'bg-surface-subtle/50 transition-colors')}>
        {/* SLM Document & Bound Forms */}
        <td className="px-4 py-3 font-semibold text-text max-w-[20rem]">
          <div className="flex items-start gap-2">
            <FilePdf className="size-4 text-primary shrink-0 mt-0.5" aria-hidden="true" />
            <div className="min-w-0">
              <div className="truncate font-bold text-sm text-text" title={item.document_title ?? 'Untitled SLM'}>
                {item.document_title ?? 'Untitled SLM'}
              </div>
              {item.bound_forms && item.bound_forms.length > 0 ? (
                <div
                  className="mt-1 flex flex-wrap items-center gap-1"
                  aria-label="Bound rubric revisions"
                >
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">
                    Revisions:
                  </span>
                  {item.bound_forms.map((form) => (
                    <span
                      key={form.agent_id}
                      className="inline-flex items-center rounded-xs bg-surface-subtle px-1.5 py-0.5 text-[10px] font-semibold text-text border border-border/80"
                      title={`${agentLabel(form.agent_id)}: set ${form.rubric_set_id}, ${form.adapter_key} v${form.adapter_version}`}
                    >
                      {form.agent_id.toUpperCase()} v{form.rubric_version}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </td>
        {/* Status */}
        <td className="px-4 py-3 whitespace-nowrap">
          <Badge
            variant={
              item.status === 'COMPLETED'
                ? 'success'
                : item.status === 'FAILED'
                  ? 'destructive'
                  : 'warning'
            }
            withDot
          >
            {item.status}
          </Badge>
        </td>
        {/* Accuracy (Exact Matches / Total Criteria) */}
        <td className="px-4 py-3 text-right whitespace-nowrap">
          {comparedCount ? (
            <div className="inline-flex items-center justify-end gap-1.5 font-mono text-xs tabular-nums">
              <span className="font-bold text-text">
                {exactMatches}/{comparedCount}
              </span>
              <span className="rounded-xs bg-surface-subtle border border-border px-1 py-0.2 text-[10px] font-medium text-text-muted">
                {((exactMatches / comparedCount) * 100).toFixed(0)}%
              </span>
            </div>
          ) : (
            <span className="text-text-muted font-medium">—</span>
          )}
        </td>

        {/* Mean Error (MAE) */}
        <td className="px-4 py-3 text-right whitespace-nowrap">
          {formatMaeBadge(item.absolute_error)}
        </td>

        {/* Latency */}
        <td className="px-4 py-3 text-right font-mono text-text-muted tabular-nums text-xs whitespace-nowrap">
          {item.latency_seconds == null ? '—' : `${item.latency_seconds.toFixed(2)} s`}
        </td>

        {/* Toxicity */}
        <td className="px-4 py-3 text-right font-mono text-text-muted tabular-nums text-xs whitespace-nowrap">
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

        {/* Action Toggle */}
        <td className="px-4 py-3 text-right whitespace-nowrap">
          {item.status === 'COMPLETED' ||
          item.status === 'FAILED' ||
          item.criterion_scores.length > 0 ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onToggle}
              aria-expanded={isExpanded}
              aria-controls={expansionId}
              className="h-7 px-2.5 text-xs font-semibold gap-1 shrink-0"
            >
              {isExpanded ? (
                <CaretDown className="size-3.5" aria-hidden="true" />
              ) : (
                <CaretRight className="size-3.5" aria-hidden="true" />
              )}
              <span>{isExpanded ? 'Hide details' : 'Open evaluation'}</span>
            </Button>
          ) : item.error_message ? (
            <span className="text-xs font-semibold text-destructive">{item.error_message}</span>
          ) : (
            <span className="text-text-muted font-medium">—</span>
          )}
        </td>
      </tr>
      {/* Expandable Benchmark Review Drawer */}
      {isExpanded ? (
        <tr>
          <td colSpan={HISTORY_COLSPAN} className="bg-surface-subtle/60 p-4 border-b border-border">
            <ValidationDetail
              id={expansionId}
              validationId={item.validation_id}
              evaluationId={item.evaluation_id}
              fallbackCriteria={item.criterion_scores}
              boundForms={item.bound_forms}
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
  boundForms?: ModelValidationItem['bound_forms'];
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
  boundForms: initialBoundForms = [],
  partialWithoutCurriculum,
  overallStatus,
  errorMessage,
  isExpanded,
  onClose,
}: ValidationDetailProps) {
  const detailQuery = useModelValidationDetail(validationId, isExpanded);
  const evaluationQuery = useModelValidationEvaluation(validationId, isExpanded);

  const boundForms = detailQuery.data?.bound_forms ?? initialBoundForms;
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
      className="space-y-4 rounded-md border border-border bg-surface p-5 shadow-none"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-text">
            Per-agent criterion detail
          </h3>
          <p className="mt-0.5 text-xs text-text-muted leading-relaxed">
            Expected human benchmark vs. actual model scores. Differences highlight areas needing prompt refinement or rubric calibration.
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={onClose}
          className="h-8 px-3 text-xs font-semibold"
        >
          Close
        </Button>
      </div>

      {boundForms && boundForms.length > 0 ? (
        <section
          aria-label="Bound rubric revisions"
          className="rounded-sm border border-border bg-surface-subtle/70 p-4 space-y-2"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-text">
              Bound rubric revisions
            </h4>
            <span className="text-[11px] font-medium text-text-muted">
              Immutable form snapshots bound at validation admission
            </span>
          </div>
          <div className="mt-2 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {boundForms.map((form) => (
              <div
                key={form.agent_id}
                className="flex flex-col gap-1 rounded-sm border border-border bg-surface p-3 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-text">{agentLabel(form.agent_id)}</span>
                  <span className="rounded-xs bg-primary-soft px-1.5 py-0.5 text-[10px] font-bold text-primary border border-primary/20">
                    Rubric v{form.rubric_version}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] text-text-muted">
                  <span>Adapter:</span>
                  <span className="font-mono font-medium text-text">
                    {form.adapter_key} (v{form.adapter_version})
                  </span>
                </div>
                <div className="flex items-center justify-between text-[10px] text-text-muted">
                  <span>Rubric set:</span>
                  <span
                    className="max-w-[12rem] truncate font-mono text-text-muted"
                    title={form.rubric_set_id}
                  >
                    {form.rubric_set_id}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {isCoordinatorSkipped ? (
        <p
          role="note"
          className="flex items-start gap-2 rounded-sm border border-warning/40 bg-warning-soft px-3.5 py-2.5 text-xs font-semibold text-text"
        >
          <Warning className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
          <span className="leading-relaxed">
            This validation ran without a curriculum reference. Coordinator curriculum-grounded
            review was skipped. SME, GAD, and ITSO scores below are from the partial run.
          </span>
        </p>
      ) : null}

      {detailQuery.isLoading ? (
        <p
          role="status"
          className="flex items-center gap-2 rounded-sm border border-border bg-surface-subtle px-3 py-2 text-xs font-semibold uppercase tracking-wider text-text-muted"
        >
          <Spinner className="size-4 animate-spin text-primary" aria-hidden="true" />
          Loading criterion detail…
        </p>
      ) : null}

      {detailQuery.isError ? (
        <p
          role="alert"
          className="rounded-sm border border-destructive/30 bg-destructive-soft px-3 py-2 text-xs font-semibold text-destructive"
        >
          {getErrorMessage(
            detailQuery.error,
            'Unable to load the criterion detail for this validation.',
          )}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {grouped.map(({ agentId, agentName, rubricVersion, criteria: agentCriteria }) => {
          const isAgentSkipped = agentId === 'coordinator' && isCoordinatorSkipped;
          const matchingBoundForm = boundForms.find((b) => b.agent_id === agentId);
          const displayRubricVersion = matchingBoundForm?.rubric_version ?? rubricVersion;

          return (
            <article key={agentId} className="overflow-hidden rounded-sm border border-border bg-surface">
              <header className="flex items-center justify-between gap-2 border-b border-border bg-surface-subtle px-3.5 py-2.5">
                <div className="flex items-center gap-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-text">
                    {agentName}
                  </h4>
                  {displayRubricVersion ? (
                    <span className="rounded-xs bg-surface border border-border px-1.5 py-0.2 text-[10px] font-mono font-semibold text-text-muted tabular-nums">
                      Rubric v{displayRubricVersion}
                    </span>
                  ) : null}
                </div>
                {isAgentSkipped ? (
                  <span className="inline-flex items-center gap-1 rounded-xs bg-surface px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-text-muted border border-border">
                    <ShieldWarning className="size-3 text-warning" aria-hidden="true" />
                    Skipped — no curriculum
                  </span>
                ) : null}
              </header>
              {isAgentSkipped ? (
                <p className="px-4 py-3 text-xs font-medium leading-relaxed text-text-muted">
                  Coordinator scoring was skipped for this run. No expected, actual, or error values
                  are reported.
                </p>
              ) : (
                <table className="w-full border-collapse text-left text-xs">
                  <thead className="bg-surface text-[10px] font-bold uppercase tracking-wider text-text-muted border-b border-border">
                    <tr>
                      <th className="px-3 py-2">Criterion</th>
                      <th className="px-3 py-2 text-right">Expected</th>
                      <th className="px-3 py-2 text-right">Actual</th>
                      <th className="px-3 py-2 text-right">Error</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {agentCriteria.map((score) => {
                      const expected = score.expected_score;
                      const actual = score.actual_score;
                      const error = score.absolute_error;
                      const actualLabel =
                        actual == null ? (isTerminal ? 'Unavailable' : 'Pending') : String(actual);
                      const errorLabel =
                        error == null ? (isTerminal ? 'Unavailable' : 'Pending') : error.toFixed(2);
                      const isExactMatch = error === 0;

                      return (
                        <tr key={score.expected_score_id} className="hover:bg-surface-subtle/50 transition-colors">
                          <th scope="row" className="px-3 py-2.5 font-semibold text-text">
                            <span className="block break-words">
                              {score.criterion_id} · {score.criterion_title}
                            </span>
                          </th>
                          <td className="px-3 py-2.5 text-right font-mono font-semibold tabular-nums text-text">
                            {expected}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono font-semibold tabular-nums text-text">
                            {actual == null ? (
                              <span
                                className={cn(
                                  'inline-block rounded-xs px-1.5 py-0.2 text-[10px] font-bold uppercase tracking-wider',
                                  isTerminal
                                    ? 'bg-destructive-soft text-destructive border border-destructive/20'
                                    : 'bg-surface-subtle text-text-muted border border-border',
                                )}
                              >
                                {actualLabel}
                              </span>
                            ) : (
                              actualLabel
                            )}
                          </td>
                          <td className="px-3 py-2.5 text-right tabular-nums whitespace-nowrap">
                            {error == null ? (
                              <span
                                className={cn(
                                  'inline-block rounded-xs px-1.5 py-0.2 text-[10px] font-bold uppercase tracking-wider',
                                  isTerminal
                                    ? 'bg-destructive-soft text-destructive border border-destructive/20'
                                    : 'bg-surface-subtle text-text-muted border border-border',
                                )}
                              >
                                {errorLabel}
                              </span>
                            ) : (
                              <span
                                className={cn(
                                  'inline-flex items-center gap-1 font-mono font-bold text-xs',
                                  isExactMatch ? 'text-success' : 'text-warning',
                                )}
                              >
                                <span>{errorLabel}</span>
                                <span className="text-[10px] font-bold">
                                  {isExactMatch ? '✓' : '⚠'}
                                </span>
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                    {agentCriteria.length === 0 ? (
                      <tr>
                        <td
                          colSpan={4}
                          className="px-3 py-3 text-center text-xs font-medium text-text-muted"
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
          <p className="rounded-sm border border-border bg-surface-subtle px-3 py-2 text-xs font-semibold text-text-muted">
            No criteria have been recorded for this validation yet.
          </p>
        ) : null}
      </div>

      <section
        aria-label="Linked evaluation"
        className="grid gap-3 rounded-sm border border-border bg-surface-subtle/50 p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2.5">
          <h3 className="text-xs font-bold uppercase tracking-wider text-text">
            Linked evaluation
          </h3>
          {evaluation ? (
            <span
              className={`inline-flex rounded-xs px-2 py-0.5 text-xs font-bold ${statusClass(evaluation.status as ModelValidationItem['status'])}`}
            >
              {evaluation.status}
            </span>
          ) : evaluationQuery.isLoading ? (
            <span className="inline-flex items-center gap-2 text-xs font-semibold text-text-muted">
              <Spinner className="size-3 animate-spin text-primary" aria-hidden="true" />
              Loading evaluation status…
            </span>
          ) : null}
        </div>
        <p className="text-xs leading-relaxed text-text-muted">
          The evaluation job is accessed through the admin-linked evaluation endpoint so admins can
          review benchmark runs that another admin submitted.
        </p>
        {evaluationQuery.isError ? (
          <p
            role="alert"
            className="rounded-sm border border-destructive/30 bg-destructive-soft px-3 py-2 text-xs font-semibold text-destructive"
          >
            {getErrorMessage(
              evaluationQuery.error,
              'Unable to load the linked evaluation for this validation.',
            )}
          </p>
        ) : null}
        {evaluation ? (
          <dl className="grid gap-2 sm:grid-cols-2 text-xs">
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
        'flex flex-wrap items-baseline justify-between gap-2 rounded-xs border border-border/70 bg-surface px-3 py-2',
        fullWidth && 'sm:col-span-2',
        error && 'border-destructive/30 bg-destructive-soft text-destructive',
      )}
    >
      <dt className="text-[11px] font-semibold text-text-muted">{label}</dt>
      <dd
        className={cn(
          'text-xs font-semibold text-text',
          mono && 'font-mono',
          emphasize && 'text-primary',
          error && 'text-destructive',
        )}
      >
        {value}
      </dd>
    </div>
  );
}
