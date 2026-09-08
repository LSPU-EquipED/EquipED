export type EvaluationLifecycleStatus =
  | 'SUBMITTED'
  | 'PREPROCESSING'
  | 'EVALUATING'
  | 'SYNTHESIZING'
  | 'COMPLETED'
  | 'FAILED'
  | 'PENDING'
  | 'PROCESSING';

export interface LatestEvaluationItem {
  document_id: string;
  evaluation_id: string;
  status: string;
  submitted_at: string;
  completed_at?: string | null;
  error_message?: string | null;
}
export type TargetAgent = 'sme' | 'coordinator' | 'gad' | 'itso';

export const TARGET_AGENTS: readonly TargetAgent[] = ['sme', 'coordinator', 'gad', 'itso'];

export function isTargetAgent(value: string | null | undefined): value is TargetAgent {
  return value === 'sme' || value === 'coordinator' || value === 'gad' || value === 'itso';
}

export interface TargetAgentMeta {
  id: TargetAgent;
  shortLabel: string;
  fullName: string;
  requirement: string;
  requiresCurriculum: boolean;
}

export const TARGET_AGENT_META: Record<TargetAgent, TargetAgentMeta> = {
  sme: {
    id: 'sme',
    shortLabel: 'SME',
    fullName: 'Subject Matter Expert (SME)',
    requirement: 'Reviews discipline accuracy directly from the SLM text. No curriculum reference required.',
    requiresCurriculum: false,
  },
  coordinator: {
    id: 'coordinator',
    shortLabel: 'Coordinator',
    fullName: 'Program Coordinator',
    requirement: 'Reviews curriculum alignment. Requires a verified curriculum reference.',
    requiresCurriculum: true,
  },
  gad: {
    id: 'gad',
    shortLabel: 'GAD',
    fullName: 'GAD Unit',
    requirement: 'Reviews gender and development responsiveness directly from the SLM text. No curriculum reference required.',
    requiresCurriculum: false,
  },
  itso: {
    id: 'itso',
    shortLabel: 'ITSO',
    fullName: 'ITSO',
    requirement: 'Reviews intellectual property and citation practice directly from the SLM text. No curriculum reference required.',
    requiresCurriculum: false,
  },
};

export interface LatestEvaluationsResponse {
  items: LatestEvaluationItem[];
}
