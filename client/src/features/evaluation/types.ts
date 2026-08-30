export type EvaluationStatus =
  | 'SUBMITTED'
  | 'PREPROCESSING'
  | 'EVALUATING'
  | 'SYNTHESIZING'
  | 'COMPLETED'
  | 'FAILED';

export interface EvaluationSubmitRequest {
  document_id: string;
  syllabus_id?: string | null;
  curriculum_id?: string | null;
  partial_without_curriculum: boolean;
  confirmed_program: string;
}

export type CriterionReviewerCorrection = {
  action: 'EDIT' | 'REJECT';
  score: number | null;
  justification: string | null;
};

export interface EvaluationFormCriterionPresentation {
  rubric_criterion_id: string;
  criterion_code: string;
  title: string;
  description: string;
  display_order: number;
}

export interface EvaluationFormDomainPresentation {
  rubric_domain_id: string;
  code: string;
  title: string;
  display_order: number;
  criteria: EvaluationFormCriterionPresentation[];
}

export interface EvaluationFormPresentation {
  form_snapshot_id: string;
  rubric_set_id: string;
  version: number;
  snapshot_hash: string;
  adapter_key: string;
  adapter_version: number;
  domains: EvaluationFormDomainPresentation[];
}

export interface CriterionScoreItem {
  rubric_criterion_id?: string | null;
  criterion_id: string;
  criterion_text: string;
  description?: string | null;
  display_order?: number | null;
  score: number;
  justification: string;
  evidence?: string | null;
  is_ungrounded?: boolean;
  reviewer_correction?: CriterionReviewerCorrection | null;
}

export interface DomainScoreBlock {
  form_snapshot_id?: string | null;
  rubric_set_id?: string | null;
  version?: number | null;
  snapshot_hash?: string | null;
  adapter_key?: string | null;
  adapter_version?: number | null;
  domain_id?: string | null;
  domain_name?: string | null;
  domain_display_order?: number | null;
  criteria: CriterionScoreItem[];
  subtotal: number;
  max_score: number;
  status: string;
  adjectival_rating?: string | null;
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
  document_title?: string | null;
  program?: string | null;
  synthesized_score: number;
  overall_score?: number | null;
  adjectival_rating?: string | null;
  domain_scores: Record<string, DomainScoreBlock>;
  flags: EvaluationFlagItem[];
  active_agents: string[];
  failed_agents: string[];
  is_partial: boolean;
  partial_reason?: string | null;
  evaluation_status: string;
  submitted_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  forms?: Record<string, EvaluationFormPresentation>;
  legacy_notice?: string | null;
}

export type CriterionFeedbackAction = 'ACCEPT' | 'REJECT' | 'EDIT';

export interface CriterionFeedbackRequest {
  agent_name: 'itso' | 'sme';
  action: CriterionFeedbackAction;
  score?: number;
  justification?: string;
  notes?: string;
}

export interface CriterionFeedbackResponse {
  log_id: string;
  evaluation_id: string;
  user_id: string;
  agent_name: string | null;
  criterion_id: string | null;
  action: CriterionFeedbackAction;
  edited_json: { score: number; justification: string } | null;
  notes: string | null;
  created_at: string;
}
