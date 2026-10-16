export interface ArchivedOutput {
  score: number;
  status: 'ok' | 'repaired' | 'fallback' | 'unavailable';
  evidence: string[] | null;
  reasoning: string | null;
  stored_justification: string | null;
}
export interface ArchivedCriterion {
  id: string;
  title: string;
  expected: number;
  base: ArchivedOutput;
  adapter: ArchivedOutput;
  audit_note: string | null;
}
export interface ArchivedComparison {
  title: string;
  base_validation_id: string;
  adapter_validation_id: string;
  base_evaluation_id: string;
  adapter_evaluation_id: string;
  prompt_hashes: { criteria: string[]; sha256: string }[];
  criteria: ArchivedCriterion[];
}
export interface ArchivedExperiment {
  id: string;
  title: string;
  adapter_label: string;
  scope: string;
  reference_kind: string;
  pair_count: number | null;
  dataset_note: string;
  summary: string;
  limitations: string[];
  primary_criteria: string[] | null;
  training: {
    steps: number;
    epochs: number;
    first_loss: number;
    last_loss: number;
    first_margin: number;
    last_margin: number;
  } | null;
  runs: ArchivedComparison[];
}
export interface FineTuningArchive {
  schema_version: number;
  archived_on: string;
  experiments: ArchivedExperiment[];
}
