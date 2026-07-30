export interface ModelValidationCriterionScore {
  expected_score_id: string;
  agent_id: string;
  criterion_id: string;
  criterion_title: string;
  expected_score: number;
  actual_score: number | null;
  absolute_error: number | null;
}

export interface ModelValidationItem {
  validation_id: string;
  evaluation_id: string;
  document_id: string;
  document_title: string | null;
  partial_without_curriculum: boolean;
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
  agent_confusion_matrices: Record<'sme' | 'coordinator' | 'gad' | 'itso', number[][]>;
}

export interface ModelValidationCreateBody {
  document_id: string;
  curriculum_id?: string;
  partial_without_curriculum?: boolean;
  expected_scores: Array<{
    agent_id: 'sme' | 'coordinator' | 'gad' | 'itso';
    criterion_id: string;
    expected_score: number;
  }>;
}

export interface ModelValidationCriterionDefinition {
  criterion_id: string;
  title: string;
  description: string;
  domain_title: string;
}

export interface ModelValidationAgentCriteria {
  agent_id: 'sme' | 'coordinator' | 'gad' | 'itso';
  agent_name: string;
  rubric_version: number;
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
  status: 'SUBMITTED' | 'PREPROCESSING' | 'EVALUATING' | 'SYNTHESIZING' | 'COMPLETED' | 'FAILED';
  error_message: string | null;
  partial_without_curriculum: boolean;
  partial_reason: string | null;
  submitted_by: string | null;
  submitted_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
}
