import type { ArchivedExperiment } from '../archiveTypes';
import { archiveMetrics } from './archiveMetrics';

export function fineTunedModelLabel(label: string) {
  return `Fine-tuned SME model ${label.split('-').at(-1) ?? label}`;
}

export function experimentResultSummary(experiment: ArchivedExperiment) {
  if (experiment.id === 'v7') {
    const m = archiveMetrics(experiment);
    return `The fine-tuned SME model scored closer to the synthetic targets across the ${experiment.runs.length} original comparisons. MAE decreased from ${m.baseMae?.toFixed(2)} to ${m.adapterMae?.toFixed(2)}, with exact matches increasing from ${m.baseExact} to ${m.adapterExact} out of ${m.count} criterion scores. These original single-run comparisons show a small observed gain.`;
  }
  if (experiment.id === 'v9') {
    return 'The fine-tuned SME model produced some explanations that better distinguished lesson content from student activities, but this improvement was inconsistent across repeated runs.';
  }
  if (experiment.id === 'v13') {
    return 'The fine-tuned SME model produced more complete evidence citations in some cases. OP-05 scoring error remained unchanged after training.';
  }
  return experiment.summary;
}
