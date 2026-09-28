import { Warning } from '@phosphor-icons/react';
import { getErrorMessage } from '@equiped/api-client';
import { Skeleton } from '@equiped/ui';
import { useModelValidationDetail } from '../hooks/useModelValidationQueries';
import type { ModelValidationCriterionScore, ModelValidationItem } from '../types';
import { agentLabel, groupCriteriaByAgent } from '../utils/helpers';
import { ValidationLinkedEvaluation } from './ValidationLinkedEvaluation';
import { ValidationAgentScores } from './ValidationAgentScores';

type ValidationDetailProps = {
  id: string;
  validationId: string;
  fallbackCriteria: ModelValidationCriterionScore[];
  boundForms?: ModelValidationItem['bound_forms'];
  partialWithoutCurriculum: boolean;
  overallStatus: ModelValidationItem['status'];
  errorMessage: string | null;
  isExpanded: boolean;
};

export function ValidationDetail({
  id,
  validationId,
  fallbackCriteria,
  boundForms: initialBoundForms = [],
  partialWithoutCurriculum,
  overallStatus,
  errorMessage,
  isExpanded,
}: ValidationDetailProps) {
  const detailQuery = useModelValidationDetail(validationId, isExpanded);

  const boundForms = detailQuery.data?.bound_forms ?? initialBoundForms;
  const criteria = detailQuery.data?.criterion_scores?.length
    ? detailQuery.data.criterion_scores
    : fallbackCriteria;
  const grouped = groupCriteriaByAgent(criteria);
  const isTerminal = overallStatus === 'COMPLETED' || overallStatus === 'FAILED';
  const isCoordinatorSkipped = partialWithoutCurriculum;

  return (
    <section
      id={id}
      role="region"
      aria-label={`Validation details for ${validationId}`}
      className="space-y-5"
    >
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
        <div
          role="status"
          aria-label="Loading criterion detail"
          className="space-y-3 rounded-sm border border-border bg-surface-subtle px-3 py-3"
        >
          <Skeleton className="h-3 w-40" />
          <Skeleton className="h-4 w-full max-w-2xl" />
          <Skeleton className="h-4 w-4/5 max-w-xl" />
        </div>
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
            <ValidationAgentScores
              key={agentId}
              agentName={agentName}
              displayRubricVersion={displayRubricVersion}
              criteria={agentCriteria}
              isAgentSkipped={isAgentSkipped}
              isTerminal={isTerminal}
            />
          );
        })}
        {grouped.length === 0 ? (
          <p className="rounded-sm border border-border bg-surface-subtle px-3 py-2 text-xs font-semibold text-text-muted">
            No criteria have been recorded for this validation yet.
          </p>
        ) : null}
      </div>

      <ValidationLinkedEvaluation
        validationId={validationId}
        isExpanded={isExpanded}
        errorMessage={errorMessage}
      />
    </section>
  );
}
