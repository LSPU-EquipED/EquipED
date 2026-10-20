import type { CoordinatorAlignmentAdvisory } from "./evaluations";
import type { ITSOCriterionAssessment } from "./itso";

export interface MatrixCriterionScoreItem {
  rubric_criterion_id?: string | null;
  criterion_id: string;
  criterion_text: string;
  description?: string | null;
  display_order?: number | null;
  score: number | null;
  justification?: string;
  evidence?: string | null;
  is_ungrounded?: boolean;
}

export interface LegacyMatrixDomainScoreBlock {
  contract?: "legacy.v1";
  advisory_outputs?: CoordinatorAlignmentAdvisory | null;
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

export type ITSOMatrixDomainScoreBlock = Omit<
  LegacyMatrixDomainScoreBlock,
  "contract" | "criteria" | "subtotal"
> & {
  contract: "itso_evidence.v1";
  evaluation_id: string;
  execution_status: "COMPLETED" | "FAILED";
  scoring_complete: boolean;
  criteria: ITSOCriterionAssessment[];
  subtotal: number | null;
  scored_count: number;
  unscored_count: number;
  issue_count: number;
  uncertainty_count: number;
};
export type MatrixDomainScoreBlock =
  LegacyMatrixDomainScoreBlock | ITSOMatrixDomainScoreBlock;

export interface MonitoringMatrixRow {
  matrix_id: string;
  document_id: string;
  evaluation_id: string | null;
  faculty_name: string | null;
  program: string | null;
  document_title: string | null;
  evaluation_status: string;
  synthesized_score: number | null;
  adjectival_rating?: string | null;
  domain_scores: Record<string, MatrixDomainScoreBlock> | null;
  flag_count: number;
  feedback_status: string;
  last_updated: string;
}

export interface MatrixMetrics {
  completed_count: number;
  passing_count: number;
  flagged_count: number;
  total_flags: number;
  quality_pass_rate: number | null;
}

export interface MatrixListResponse {
  items: MonitoringMatrixRow[];
  total: number;
  page: number;
  page_size: number;
  metrics: MatrixMetrics;
}
