import type { ArchivedCriterion, ArchivedExperiment } from '../archiveTypes';

export function archiveMetrics(
  experiment: ArchivedExperiment,
  criteria = experiment.runs.flatMap((run) => run.criteria),
) {
  const included = criteria.filter(
    (c) =>
      (!experiment.primary_criteria || experiment.primary_criteria.includes(c.id)) &&
      ['ok', 'repaired'].includes(c.base.status) &&
      ['ok', 'repaired'].includes(c.adapter.status),
  );
  const error = (c: ArchivedCriterion, variant: 'base' | 'adapter') =>
    Math.abs(c[variant].score - c.expected);
  const baseError = included.reduce((sum, c) => sum + error(c, 'base'), 0);
  const adapterError = included.reduce((sum, c) => sum + error(c, 'adapter'), 0);
  return {
    count: included.length,
    baseMae: included.length ? baseError / included.length : null,
    adapterMae: included.length ? adapterError / included.length : null,
    baseExact: included.filter((c) => error(c, 'base') === 0).length,
    adapterExact: included.filter((c) => error(c, 'adapter') === 0).length,
    reduction: baseError > 0 ? ((baseError - adapterError) / baseError) * 100 : null,
    closer: included.filter((c) => error(c, 'adapter') < error(c, 'base')).length,
    unchanged: included.filter((c) => error(c, 'adapter') === error(c, 'base')).length,
    farther: included.filter((c) => error(c, 'adapter') > error(c, 'base')).length,
  };
}
