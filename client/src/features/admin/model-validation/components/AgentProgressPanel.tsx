import { CheckCircle, Loader2 } from 'lucide-react';
import type { ModelValidationItem } from '../types';
import { statusClass, validationAgents } from '../utils/helpers';

export function AgentProgressPanel({ validation }: { validation: ModelValidationItem }) {
  const isEvaluating = validation.status === 'EVALUATING';
  const agentsEvaluated = validation.status === 'SYNTHESIZING';

  return (
    <section
      aria-live="polite"
      aria-label={`Agent progress for ${validation.document_title ?? 'Model Validation'}`}
      className="overflow-hidden rounded-sm border border-slate-200 bg-white"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-5 py-4">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-800">
            Agent evaluation progress
          </h2>
          <p className="mt-1 text-xs font-medium text-slate-600">
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

      <div className="grid gap-px bg-slate-200 sm:grid-cols-2 xl:grid-cols-4">
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
            <div key={agent.id} className="flex min-h-28 items-center gap-3 bg-white p-4">
              {isSkipped || agentsEvaluated ? (
                <CheckCircle
                  className={`size-5 shrink-0 ${isSkipped ? 'text-slate-400' : 'text-[#3b963e]'}`}
                  aria-hidden="true"
                />
              ) : isEvaluating ? (
                <Loader2
                  className="size-5 shrink-0 animate-spin text-[#1b3b87]"
                  aria-hidden="true"
                />
              ) : (
                <span className="size-3 shrink-0 rounded-full border-2 border-slate-400" />
              )}
              <span className="min-w-0">
                <span className="block text-sm font-bold text-slate-900">{agent.label}</span>
                <span className="mt-1 block text-xs font-semibold text-slate-600">{label}</span>
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
