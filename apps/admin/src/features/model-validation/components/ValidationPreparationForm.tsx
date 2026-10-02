import type { ModelValidationFormState } from '../hooks/useModelValidationFormState';
import { ValidationRunSetup } from './ValidationRunSetup';
import { ValidationLaunchReadiness } from './ValidationLaunchReadiness';
import { ValidationBenchmarkScores } from './ValidationBenchmarkScores';

export function ValidationPreparationForm({ form }: { form: ModelValidationFormState }) {
  const { expectedScores, criterionDefinitions, handlePrepare } = form;

  const enteredScoreCount = Object.values(expectedScores).filter(
    (val) => val && /^[1-4]$/.test(val),
  ).length;

  const totalCriteriaCount = criterionDefinitions.reduce((acc, agent) => {
    const agentCount = agent.domains?.length
      ? agent.domains.reduce((sum, d) => sum + d.criteria.length, 0)
      : (agent.criteria?.length ?? 0);
    return acc + agentCount;
  }, 0);

  return (
    <div className="rounded-md border border-border bg-surface">
      <div className="flex flex-col gap-3 border-b border-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-sm border border-primary/20 bg-primary-soft px-2 py-0.5 text-xs font-semibold text-primary">
              Controlled benchmark
            </span>
            <span className="text-xs text-text-muted">Human scoring reference</span>
          </div>
          <h2 className="mt-1 text-lg font-semibold leading-tight text-text">
            Prepare a benchmark run
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-text-muted">
            Define the model scope, attach the SLM, and enter the human benchmark for each active
            criterion.
          </p>
        </div>

        {totalCriteriaCount > 0 ? (
          <div className="flex shrink-0 items-center gap-2 rounded-sm border border-border bg-surface-subtle px-3 py-2 font-mono text-xs tabular-nums text-text">
            <span className="font-sans text-[11px] font-medium text-text-muted">Scored</span>
            <strong className="font-bold text-primary">{enteredScoreCount}</strong>
            <span className="text-text-muted">/</span>
            <span>{totalCriteriaCount} criteria</span>
          </div>
        ) : null}
      </div>

      <form onSubmit={handlePrepare} className="p-5 sm:p-6">
        <div className="grid items-start gap-6 lg:grid-cols-12">
          <div className="space-y-0 divide-y divide-border rounded-md border border-border lg:col-span-5">
            <ValidationRunSetup form={form} />
            <ValidationLaunchReadiness
              form={form}
              enteredScoreCount={enteredScoreCount}
              totalCriteriaCount={totalCriteriaCount}
            />
          </div>

          <div className="space-y-5 lg:col-span-7">
            <ValidationBenchmarkScores form={form} />
          </div>
        </div>
      </form>
    </div>
  );
}
