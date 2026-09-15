export interface MatrixCriterionScoreItem {
  rubric_criterion_id?: string | null;
  criterion_id: string;
  criterion_text: string;
  description?: string | null;
  display_order?: number | null;
  score: number;
  justification?: string;
  evidence?: string | null;
  is_ungrounded?: boolean;
}

export interface MatrixDomainScoreBlock {
  form_snapshot_id?: string | null;
  rubric_set_id?: string | null;
  version?: number | null;
  snapshot_hash?: string | null;
  adapter_key?: string | null;
  adapter_version?: number | null;
  domain_id?: string | null;
  domain_name?: string | null;
  domain_display_order?: number | null;
  criteria?: MatrixCriterionScoreItem[];
  subtotal: number;
  max_score: number;
  status: string;
  adjectival_rating?: string | null;
  summary?: string;
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
  adjectival_rating: string | null;
  domain_scores: Record<string, MatrixDomainScoreBlock> | null;
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

export interface EvaluatorAttribution {
  user_id: string | null;
  name: string;
  email: string | null;
  department: string | null;
}

export interface EvaluationFlagItem {
  flag_id: string;
  evaluation_id: string;
  agent_id: string;
  criterion_id?: string | null;
  criterion_text?: string | null;
  score?: number | null;
  justification?: string | null;
  chunk_id?: string | null;
  flag_type?: string | null;
  severity?: string | null;
  message?: string | null;
}

export interface MasterSynthesisPillar {
  weight: number;
  subtotal: number | null;
  status: string;
  criteria: MatrixCriterionScoreItem[];
  summary: string;
  evaluator: EvaluatorAttribution | null;
}

export interface MasterSynthesisDetailResponse {
  document_id: string;
  document_title: string | null;
  course_code: string | null;
  program: string | null;
  author: EvaluatorAttribution;
  synthesized_score: number | null;
  adjectival_rating: string | null;
  evaluation_status: string;
  last_updated: string | null;
  pillars: Record<string, MasterSynthesisPillar>;
  flags: EvaluationFlagItem[];
  can_certify: boolean;
}
