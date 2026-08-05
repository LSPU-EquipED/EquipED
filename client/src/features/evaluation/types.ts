export type EvaluationStatus =
  | 'SUBMITTED'
  | 'PREPROCESSING'
  | 'EVALUATING'
  | 'SYNTHESIZING'
  | 'COMPLETED'
  | 'FAILED';

export interface CriterionScoreItem {
  criterion_id: string;
  criterion_text: string;
  score: number;
  justification: string;
  evidence?: string | null;
  chunk_ids?: string | null;
}

export interface DomainScoreBlock {
  criteria: CriterionScoreItem[];
  subtotal: number;
  max_score: number;
  status: string;
  adjectival_rating?: string;
  summary?: string;
}

export interface EvaluationFlagItem {
  flag_id: string;
  evaluation_id: string;
  agent_id: string;
  criterion_id: string;
  criterion_text: string;
  score: number;
  justification?: string;
  chunk_id?: string;
}

export interface EvaluationResponse {
  evaluation_id: string;
  document_id: string;
  syllabus_id?: string | null;
  curriculum_id?: string | null;
  status: EvaluationStatus;
  error_message?: string;
  partial_without_curriculum?: boolean;
  partial_reason?: string | null;
  submitted_by?: string;
  submitted_at: string;
  completed_at?: string;
  duration_seconds?: number | null;
}

export interface EvaluationStatusResponse {
  evaluation_id: string;
  status: EvaluationStatus;
  error_message?: string;
  partial_without_curriculum?: boolean;
  partial_reason?: string | null;
  completed_at?: string;
  duration_seconds?: number | null;
}

export interface EvaluationListItem {
  evaluation_id: string;
  document_id: string;
  document_title?: string | null;
  syllabus_id?: string | null;
  curriculum_id?: string | null;
  status: EvaluationStatus;
  partial_without_curriculum?: boolean;
  partial_reason?: string | null;
  submitted_at: string;
  completed_at?: string | null;
  duration_seconds?: number | null;
}

export interface EvaluationListResponse {
  items: EvaluationListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface EvaluationResultsResponse {
  evaluation_id: string;
  document_id: string;
  syllabus_id?: string | null;
  document_title?: string;
  program?: string;
  synthesized_score: number;
  overall_score?: number;
  adjectival_rating?: string;
  domain_scores: Record<string, DomainScoreBlock>;
  flags: EvaluationFlagItem[];
  active_agents: string[];
  failed_agents: string[];
  is_partial: boolean;
  partial_reason?: string | null;
  evaluation_status: string;
  submitted_at?: string | null;
  completed_at?: string;
  duration_seconds?: number | null;
}
