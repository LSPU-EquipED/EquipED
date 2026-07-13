import type {
  DomainScoreBlock,
  PolicyArea,
  ReferenceSourceType,
} from '../../shared/types/documents';

export interface PromptVersionItem {
  version_id: string;
  version_number: number;
  prompt_text: string;
  is_active: boolean;
  updated_by: string | null;
  motivation: string | null;
  created_at: string;
}

export interface PromptVersionListResponse {
  agent_id: string;
  versions: PromptVersionItem[];
  total: number;
}

export interface PromptCreateBody {
  prompt_text: string;
  motivation?: string;
}

export interface PreferenceLogItem {
  log_id: string;
  evaluation_id: string;
  user_id: string;
  action: string;
  edited_json: Record<string, unknown> | null;
  notes: string | null;
  created_at: string;
}

export interface PreferenceLogListResponse {
  items: PreferenceLogItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminUserResponse {
  user_id: string;
  name: string;
  email: string;
  role: 'admin' | 'faculty';
  is_active: boolean;
  created_at: string;
}

export interface AdminUserListResponse {
  items: AdminUserResponse[];
  total: number;
}

export interface AdminUserCreateBody {
  name: string;
  email: string;
  password: string;
  role: 'admin' | 'faculty';
}

export interface AdminUserUpdateBody {
  name?: string;
  email?: string;
  is_active?: boolean;
}

export interface SystemSummaryResponse {
  total_documents: number;
  total_faculty: number;
  active_evaluations: number;
  failed_evaluations: number;
}

export interface MonitoringMatrixRow {
  matrix_id: string;
  document_id: string;
  evaluation_id: string | null;
  faculty_name: string | null;
  program: string | null;
  document_title: string | null;
  evaluation_status: string;
  synthesized_score: number | null;
  domain_scores: Record<string, DomainScoreBlock> | null;
  flag_count: number;
  feedback_status: string;
  last_updated: string;
}

export interface MatrixListResponse {
  items: MonitoringMatrixRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminUploadInput {
  file: File;
  sourceType: ReferenceSourceType | 'policy';
  title: string;
  program?: string;
  policyArea?: PolicyArea;
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

export interface ModelValidationCriterionScore {
  expected_score_id: string;
  agent_id: string;
  criterion_id: string;
  criterion_title: string;
  expected_score: number;
  actual_score: number | null;
  absolute_error: number | null;
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
