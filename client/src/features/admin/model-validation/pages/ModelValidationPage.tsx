import { AgentProgressPanel } from '../components/AgentProgressPanel';
import { ValidationHistoryTable } from '../components/ValidationHistoryTable';
import { ValidationPerformanceMetrics } from '../components/ValidationPerformanceMetrics';
import { ValidationPreparationForm } from '../components/ValidationPreparationForm';
import { useModelValidationFormState } from '../hooks/useModelValidationFormState';
import {
  useModelValidationHistory,
  useModelValidationMetrics,
} from '../hooks/useModelValidationQueries';
import { terminalStatuses } from '../utils/helpers';

export function ModelValidationPage() {
  const history = useModelValidationHistory();
  const activeValidations =
    history.data?.items.filter((item) => !terminalStatuses.has(item.status)) ?? [];
  const metricSummary = useModelValidationMetrics(activeValidations.length > 0);
  const formState = useModelValidationFormState();

  return (
    <section className="grid min-w-0 gap-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Admin</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-900">Model Validation</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-600">
          Run the standard multi-agent SLM evaluation against an independent human benchmark.
          Expected scores are entered for every active agent criterion, stay private from the
          evaluator agents, and use the institutional 1–4 scale.
        </p>
      </header>

      <ValidationPerformanceMetrics metricSummary={metricSummary} />

      <ValidationPreparationForm form={formState} />

      {activeValidations.map((validation) => (
        <AgentProgressPanel key={validation.validation_id} validation={validation} />
      ))}

      <ValidationHistoryTable history={history} />
    </section>
  );
}
