import { getErrorMessage } from '@equiped/api-client';
import { cn, Skeleton } from '@equiped/ui';
import { useModelValidationEvaluation } from '../hooks/useModelValidationQueries';
import type { ModelValidationItem } from '../types';
import { formatTimestamp, statusClass } from '../utils/helpers';

export function ValidationLinkedEvaluation({
  validationId,
  isExpanded,
  errorMessage,
}: {
  validationId: string;
  isExpanded: boolean;
  errorMessage: string | null;
}) {
  const evaluationQuery = useModelValidationEvaluation(validationId, isExpanded);
  const evaluation = evaluationQuery.data;
  return (
    <section
      aria-label="Linked evaluation"
      className="grid gap-3 rounded-sm border border-border bg-surface-subtle/50 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2.5">
        <h3 className="text-xs font-bold uppercase tracking-wider text-text">Linked evaluation</h3>
        {evaluation ? (
          <span
            className={`inline-flex rounded-xs px-2 py-0.5 text-xs font-bold ${statusClass(evaluation.status as ModelValidationItem['status'])}`}
          >
            {evaluation.status}
          </span>
        ) : evaluationQuery.isLoading ? (
          <span role="status" aria-label="Loading evaluation status" className="inline-flex">
            <Skeleton className="h-3 w-28" />
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
          <EvaluationMetaItem label="Submitted" value={formatTimestamp(evaluation.submitted_at)} />
          <EvaluationMetaItem label="Completed" value={formatTimestamp(evaluation.completed_at)} />
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
