export type EvaluationLifecycleStatus =
  | 'SUBMITTED'
  | 'PREPROCESSING'
  | 'EVALUATING'
  | 'SYNTHESIZING'
  | 'COMPLETED'
  | 'FAILED'
  | 'PENDING'
  | 'PROCESSING';

export interface EvaluationListStats {
  total: number;
  completed: number;
  in_progress: number;
  average_duration_seconds: number | null;
}

export interface EvaluationListItem {
  evaluation_id: string;
  document_id: string;
  document_title?: string | null;
  syllabus_id: string | null;
  curriculum_id: string | null;
  status: EvaluationLifecycleStatus | string;
  error_message: string | null;
  target_agent: TargetAgent | 'all';
  partial_without_curriculum?: boolean;
  partial_reason?: string | null;
  confirmed_program: string | null;
  submitted_by?: string | null;
  submitted_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
}

export interface EvaluationListResponse {
  items: EvaluationListItem[];
  total: number;
  page: number;
  page_size: number;
  stats?: EvaluationListStats;
}

export interface LatestEvaluationItem {
  document_id: string;
  evaluation_id: string;
  status: string;
  target_agent?: TargetAgent | 'all';
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
    fullName: 'Innovation and Technology Support Office',
    requirement: 'Reviews intellectual property and citation practice directly from the SLM text. No curriculum reference required.',
    requiresCurriculum: false,
  },
};

export interface LatestEvaluationsResponse {
  items: LatestEvaluationItem[];
}
