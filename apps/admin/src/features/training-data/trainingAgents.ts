export const TRAINING_AGENT_IDS = ['coordinator', 'sme', 'gad', 'itso'] as const;

export type TrainingAgentId = (typeof TRAINING_AGENT_IDS)[number];

export interface TrainingAgentMeta {
  readonly id: TrainingAgentId;
  readonly label: string;
}

export const TRAINING_AGENTS: readonly TrainingAgentMeta[] = [
  { id: 'coordinator', label: 'Program Coordinator' },
  { id: 'sme', label: 'Subject Matter Expert' },
  { id: 'gad', label: 'Gender & Development (GAD)' },
  { id: 'itso', label: 'Innovation and Technology Support Office' },
] as const;

export const DEFAULT_TRAINING_AGENT_ID: TrainingAgentId = 'coordinator';

export function isTrainingAgentId(value: unknown): value is TrainingAgentId {
  return typeof value === 'string' && (TRAINING_AGENT_IDS as readonly string[]).includes(value);
}
