import { CheckCircle, Spinner } from '@phosphor-icons/react';
import type { ModelValidationItem } from '../types';
import { statusClass, validationAgents } from '../utils/helpers';

export function AgentProgressPanel({ validation }: { validation: ModelValidationItem }) {
  const isEvaluating = validation.status === 'EVALUATING';
  const agentsEvaluated = validation.status === 'SYNTHESIZING';

  return (
    <section
      aria-live="polite"
      aria-label={`Agent progress for ${validation.document_title ?? 'Model Validation'}`}
      className="overflow-hidden rounded-sm border border-border bg-surface"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface-subtle px-5 py-4">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-text">
            Agent evaluation progress
          </h2>
          <p className="mt-1 text-xs font-medium text-text-muted">
            {validation.document_title ?? 'Untitled SLM'} · Same parallel scoring pipeline as
            faculty evaluation
          </p>
        </div>
        <span
          className={`rounded-sm px-2 py-1 text-xs font-bold ${statusClass(validation.status)}`}
        >
          {validation.status}
        </span>
      </div>

      <div className="grid gap-px bg-border sm:grid-cols-2 xl:grid-cols-4">
        {validationAgents.map((agent) => {
          const isSkipped = agent.id === 'coordinator' && validation.partial_without_curriculum;
          const label = isSkipped
            ? 'Skipped — no curriculum'
            : isEvaluating
              ? 'Evaluating'
              : agentsEvaluated
                ? 'Agent scoring complete'
                : 'Queued';

          return (
            <div key={agent.id} className="flex min-h-28 items-center gap-3 bg-surface p-4">
              {isSkipped || agentsEvaluated ? (
                <CheckCircle
                  className={`size-5 shrink-0 ${isSkipped ? 'text-text-muted' : 'text-success'}`}
                  aria-hidden="true"
                />
              ) : isEvaluating ? (
                <Spinner
                  className="size-5 shrink-0 animate-spin text-primary"
                  aria-hidden="true"
                />
              ) : (
                <span className="size-3 shrink-0 rounded-full border-2 border-text-muted" />
              )}
              <span className="min-w-0">
                <span className="block text-sm font-bold text-text">{agent.label}</span>
                <span className="mt-1 block text-xs font-semibold text-text-muted">{label}</span>
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
