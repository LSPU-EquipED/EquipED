export interface ModelValidationCriterionScore {
  expected_score_id: string;
  agent_id: string;
  rubric_set_id?: string | null;
  rubric_version?: number | null;
  rubric_criterion_id?: string | null;
  criterion_id: string;
  criterion_title: string;
  expected_score: number;
  actual_score: number | null;
  absolute_error: number | null;
}

export interface ModelValidationBoundForm {
  agent_id: string;
  rubric_set_id: string;
  rubric_version: number;
  adapter_key: string;
  adapter_version: number;
}

export interface ModelValidationItem {
  validation_id: string;
  evaluation_id: string;
  document_id: string;
  document_title: string | null;
  partial_without_curriculum: boolean;
  bound_forms: ModelValidationBoundForm[];
  criterion_scores: ModelValidationCriterionScore[];
  absolute_error: number | null;
  latency_seconds: number | null;
  score_perplexity: number | null;
  toxicity_score: number | null;
  toxicity_label: string | null;
  toxicity_explanation: string | null;
  toxicity_model: string | null;
  toxicity_error: string | null;
  status: 'SUBMITTED' | 'PREPROCESSING' | 'EVALUATING' | 'SYNTHESIZING' | 'COMPLETED' | 'FAILED';
  error_message: string | null;
  created_at: string;
}

export interface ModelValidationListResponse {
  items: ModelValidationItem[];
  total: number;
}

export interface ModelValidationMetricsResponse {
  completed_runs: number;
  mean_absolute_error: number | null;
  mean_latency_seconds: number | null;
  score_perplexity: number | null;
  mean_toxicity_score: number | null;
  class_labels: string[];
  confusion_matrix: number[][];
  agent_confusion_matrices: Record<string, number[][]>;
}

export interface ExpectedCriterionScoreInput {
  agent_id: 'sme' | 'coordinator' | 'gad' | 'itso';
  rubric_set_id: string;
  rubric_criterion_id: string;
  expected_score: number;
}

export interface ModelValidationCreateBody {
  document_id: string;
  syllabus_id?: string | null;
  curriculum_id?: string | null;
  partial_without_curriculum: boolean;
  expected_scores: ExpectedCriterionScoreInput[];
}

export interface ModelValidationCriterionDefinition {
  rubric_criterion_id: string;
  criterion_code: string;
  criterion_id?: string | null;
  title: string;
  description: string;
  domain_title?: string | null;
  display_order: number;
}

export interface ModelValidationDomainDefinition {
  rubric_domain_id: string;
  code: string;
  title: string;
  display_order: number;
  criteria: ModelValidationCriterionDefinition[];
}

export interface ModelValidationAgentCriteria {
  agent_id: 'sme' | 'coordinator' | 'gad' | 'itso' | string;
  agent_name: string;
  rubric_set_id: string;
  rubric_version: number;
  domains: ModelValidationDomainDefinition[];
  criteria: ModelValidationCriterionDefinition[];
}

export interface ModelValidationCriteriaResponse {
  agents: ModelValidationAgentCriteria[];
  total_criteria: number;
}

export interface AdminEvaluationResponse {
  evaluation_id: string;
  document_id: string;
  syllabus_id: string | null;
  curriculum_id: string | null;
  status:
    | 'SUBMITTED'
    | 'PREPROCESSING'
    | 'EVALUATING'
    | 'SYNTHESIZING'
    | 'COMPLETED'
    | 'FAILED'
    | string;
  error_message: string | null;
  partial_without_curriculum: boolean;
  partial_reason: string | null;
  confirmed_program?: string | null;
  submitted_by: string | null;
  submitted_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
}
